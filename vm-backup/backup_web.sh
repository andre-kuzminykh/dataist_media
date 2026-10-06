#!/usr/bin/env bash
# backup_web.sh — снапшот сайта dataist.ai (сервис web) НА VM, чтобы можно было
# откатиться одной командой (restore_web.sh). Брат-близнец backup_local.sh,
# который снимает бота dataist_media; этот — сайт.
#
# Запускать на VM:  sudo bash backup_web.sh
#
# Сайт во время бэкапа НЕ останавливается и НЕ перезапускается: скрипт только
# читает (git, docker inspect, копии файлов) и пишет в свой каталог снапшота.
# Тяжёлые шаги идут с nice/ionice, чтобы не отнимать процессор и диск у сайта.
#
# Складывает в /opt/dataist_backups/web_<timestamp>/ :
#   SNAPSHOT.txt         — что сохранено и итог проверки (kind=full|partial|interrupted)
#   SHA256SUMS.txt       — контрольные суммы всех файлов снапшота
#   app_head.txt         — коммит и ветка dataist-ai, из которых развёрнут сайт, + git status
#   app.bundle           — git-бандл каталога приложения (все ветки и история)
#   app_worktree.tar.gz  — рабочее дерево как развёрнуто (без .git), с незакоммиченными правками
#   app.env              — .env приложения: ADMIN_TOKEN, INDEXNOW_KEY и др. (в git его нет!)
#   image.txt            — какой образ работал и под каким тегом он сохранён
#   image.tar.gz         — сам образ (docker save): откат, даже если тег подчистит prune
#   db/                  — согласованные копии баз SQLite (аналитика) через backup API
#   web_data.tar.gz      — том с данными сайта (/app/data) целиком
#   content_head.txt     — какой коммит контента (dataist) сейчас на сайте
#   content.bundle       — (только при WITH_CONTENT=1) полная копия контент-репозитория
#   proxy/               — конфиги Caddy / nginx хоста и crontab
#   container.json       — docker inspect работающего контейнера
#   health.json          — ответ /api/v1/admin/health в момент снапшота
#
# Переключатели (через окружение):
#   APP_DIR=/path        — каталог приложения, если автопоиск не справился
#   WITH_IMAGE=0         — не делать docker save (тег образа ставится всё равно)
#   WITH_CONTENT=1       — добавить полный бандл контент-репозитория (~2.5 ГБ+)
#   BACKUP_ROOT=/path    — куда складывать (по умолчанию /opt/dataist_backups)
#   MIN_FREE_MB=2048     — сколько МБ обязано остаться свободным после бэкапа
set -Eeuo pipefail

BACKUP_ROOT=${BACKUP_ROOT:-/opt/dataist_backups}
TS=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_ROOT/web_$TS"
WITH_IMAGE=${WITH_IMAGE:-1}
WITH_CONTENT=${WITH_CONTENT:-0}
APP_DIR=${APP_DIR:-}
BACKUP_IMAGE_REPO=dataist-web-backup

if [ "$(id -u)" -ne 0 ]; then
    echo "Запустите от root: sudo bash $0" >&2
    exit 1
fi
command -v docker >/dev/null 2>&1 || { echo "нет docker" >&2; exit 1; }

# Каталоги приложения и контента принадлежат обычному пользователю, а скрипт
# идёт от root — без safe.directory git откажется их читать («dubious ownership»).
GIT=(git -c "safe.directory=*")

# Самый низкий приоритет процессора и диска для всего тяжёлого: сайт делит
# машину с десятком сервисов, и бэкап не должен у них ничего отнимать.
LOW="nice -n 19"
command -v ionice >/dev/null 2>&1 && LOW="$LOW ionice -c3"

log()  { echo "--- $*"; }
warn() { echo "  ВНИМАНИЕ: $*" >&2; }

# ---------------------------------------------------------------------------
# 1. Где сайт
# ---------------------------------------------------------------------------
# Ищем НЕ по имени контейнера (его задаёт имя каталога, и на машине есть
# другие проекты со службой web), а по меткам compose: служба web, в рабочем
# каталоге которой лежат web/main.py и scripts/deploy_web.sh — это наш сайт.
CID=""
for c in $(docker ps -q --filter label=com.docker.compose.service=web); do
    wd=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$c" 2>/dev/null || true)
    [ -n "$wd" ] || continue
    if [ -n "$APP_DIR" ] && [ "$(readlink -f "$wd")" != "$(readlink -f "$APP_DIR")" ]; then
        continue
    fi
    if [ -f "$wd/web/main.py" ] && [ -f "$wd/scripts/deploy_web.sh" ]; then
        CID=$c
        APP_DIR=$wd
        break
    fi
done
# Старый docker-compose (v1) не ставит метку working_dir — тогда по явно
# указанному APP_DIR спрашиваем сам compose.
if [ -z "$CID" ] && [ -n "$APP_DIR" ] && [ -f "$APP_DIR/docker-compose.yml" ]; then
    CID=$(cd "$APP_DIR" && { docker compose ps -q web 2>/dev/null || docker-compose ps -q web 2>/dev/null; } | head -1 || true)
fi

if [ -z "$APP_DIR" ]; then
    echo "Не нашёл работающий контейнер сайта (служба web с web/main.py)." >&2
    echo "Укажите каталог приложения явно: sudo APP_DIR=/path/to/dataist-ai bash $0" >&2
    exit 1
fi
[ -f "$APP_DIR/web/main.py" ] || { echo "$APP_DIR — не каталог сайта (нет web/main.py)" >&2; exit 1; }

PROJECT=""; IMAGE_ID=""; IMAGE_NAME=""; DATA_VOLUME=""; CONTENT_DIR=""; HOST_PORT=""
if [ -n "$CID" ]; then
    PROJECT=$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$CID")
    IMAGE_ID=$(docker inspect -f '{{.Image}}' "$CID")
    IMAGE_NAME=$(docker inspect -f '{{.Config.Image}}' "$CID")
    DATA_VOLUME=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/data"}}{{.Name}}{{end}}{{end}}' "$CID")
    CONTENT_DIR=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/app/content"}}{{.Source}}{{end}}{{end}}' "$CID")
    HOST_PORT=$(docker port "$CID" 8080/tcp 2>/dev/null | head -1 | awk -F: '{print $NF}' || true)
else
    warn "контейнер сайта не запущен — образ и живые данные сохранить не получится, только код и env"
    PROJECT=$(basename "$APP_DIR" | tr '[:upper:]' '[:lower:]')
    DATA_VOLUME="${PROJECT}_web_data"
    docker volume inspect "$DATA_VOLUME" >/dev/null 2>&1 || DATA_VOLUME=""
fi

echo "=== Бэкап сайта"
echo "  приложение : $APP_DIR (compose-проект ${PROJECT:-?})"
echo "  контейнер  : ${CID:-нет}"
echo "  образ      : ${IMAGE_NAME:-?} ${IMAGE_ID:+(${IMAGE_ID:7:12})}"
echo "  данные     : том ${DATA_VOLUME:-?}"
echo "  контент    : ${CONTENT_DIR:-?}"
echo "  снапшот    : $DEST"

# ---------------------------------------------------------------------------
# 2. Хватит ли места — ДО того, как что-то писать
# ---------------------------------------------------------------------------
# Заполненный диск роняет всё сразу: SQLite перестаёт писать, docker не
# может создать слой, сайт падает. Поэтому бэкап считает худший случай и
# отказывается заранее, а не на середине.
mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT"

mb_of() { { du -sm "$@" 2>/dev/null || true; } | awk '{s+=$1} END {print s+0}'; }
NEED_MB=0
APP_MB=$(mb_of "$APP_DIR")                       # с .git: бандл + дерево
NEED_MB=$((NEED_MB + APP_MB))
if [ -n "$CID" ]; then
    DATA_MB=$(docker exec "$CID" du -sm /app/data 2>/dev/null | awk '{print $1+0}' || true)
    # Том + копии баз + временная копия базы внутри контейнера (до docker cp).
    NEED_MB=$((NEED_MB + 3 * ${DATA_MB:-0}))
    if [ "$WITH_IMAGE" = "1" ]; then
        IMG_BYTES=$(docker image inspect -f '{{.Size}}' "$IMAGE_ID" 2>/dev/null || true)
        NEED_MB=$((NEED_MB + ${IMG_BYTES:-0} / 1048576))   # без учёта сжатия — худший случай
    fi
fi
if [ "$WITH_CONTENT" = "1" ] && [ -n "$CONTENT_DIR" ]; then
    NEED_MB=$((NEED_MB + $(mb_of "$CONTENT_DIR/.git")))
fi
FREE_MB=$(df -Pm "$BACKUP_ROOT" | awk 'NR==2 {print $4}')
# Сколько обязано остаться свободным ПОСЛЕ бэкапа — на логи, рост базы
# аналитики и слои docker при следующем деплое.
RESERVE_MB=${MIN_FREE_MB:-2048}
echo "  нужно до ~${NEED_MB} МБ, свободно ${FREE_MB} МБ, после бэкапа должно остаться ≥ ${RESERVE_MB} МБ"
if [ "$FREE_MB" -lt $((NEED_MB + RESERVE_MB)) ]; then
    echo "" >&2
    echo "ОТКАЗ: места мало. Бэкап мог бы заполнить диск и уронить сайт." >&2
    echo "Варианты: освободить место; снять без образа: sudo WITH_IMAGE=0 bash $0;" >&2
    echo "          или писать на другой диск: sudo BACKUP_ROOT=/mnt/другой bash $0" >&2
    exit 1
fi

mkdir -p "$DEST"
chmod 700 "$DEST"

# Прерывание посреди записи оставило бы недописанный архив — на тесном диске
# худший мусор. Убираем ровно его и честно помечаем снапшот неполным.
CURRENT_FILE=""
_on_interrupt() {
    echo "" >&2
    echo "--- прервано: подчищаю недописанное ---" >&2
    [ -n "$CURRENT_FILE" ] && rm -f "$CURRENT_FILE" && echo "  удалён неполный $CURRENT_FILE" >&2
    echo "kind=interrupted" > "$DEST/SNAPSHOT.txt"
    echo "СНАПШОТ НЕПОЛНЫЙ (прерван): $DEST — полагаться на него нельзя." >&2
    exit 130
}
trap _on_interrupt INT TERM

# Любой непредвиденный сбой — честное «не завершён» вместо молчаливого
# обрыва: сайт бэкап только читает, поэтому сломаться может лишь сам бэкап.
_on_error() {
    # В подоболочке молчим: она завершится с ошибкой, и сработает ловушка
    # основного процесса — сообщение будет одно.
    [ "$BASH_SUBSHELL" -eq 0 ] || return 0
    echo "" >&2
    echo "ОШИБКА (строка $1): бэкап не завершён. Сайт это не затронуло." >&2
    [ -n "$CURRENT_FILE" ] && rm -f "$CURRENT_FILE"
    echo "kind=failed" > "$DEST/SNAPSHOT.txt"
    echo "Неполный снапшот: $DEST — полагаться на него нельзя (удалить: sudo rm -rf $DEST)" >&2
}
trap '_on_error $LINENO' ERR

# ---------------------------------------------------------------------------
# 3. Состояние: что именно сейчас работает
# ---------------------------------------------------------------------------
log "состояние"
APP_COMMIT=$("${GIT[@]}" -C "$APP_DIR" rev-parse HEAD 2>/dev/null || echo unknown)
APP_BRANCH=$("${GIT[@]}" -C "$APP_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)
{
    echo "commit=$APP_COMMIT"
    echo "branch=$APP_BRANCH"
    echo "--- git log -1"
    "${GIT[@]}" -C "$APP_DIR" log -1 --format='%H %ci %s' 2>/dev/null || true
    echo "--- git status --porcelain (правки на VM, которых нет в git)"
    "${GIT[@]}" -C "$APP_DIR" status --porcelain 2>/dev/null || true
} > "$DEST/app_head.txt"
LOCAL_EDITS=$("${GIT[@]}" -C "$APP_DIR" status --porcelain --untracked-files=no 2>/dev/null | wc -l || true)
echo "  код: $APP_BRANCH @ ${APP_COMMIT:0:12} (правок на VM в отслеживаемых файлах: $LOCAL_EDITS)"

if [ -n "$CID" ]; then
    docker inspect "$CID" > "$DEST/container.json"
    if [ -n "$HOST_PORT" ]; then
        curl -fsS --max-time 15 "http://127.0.0.1:$HOST_PORT/api/v1/admin/health" \
            > "$DEST/health.json" 2>/dev/null || warn "health не ответил (это не мешает бэкапу)"
    fi
fi
docker ps -a --format '{{.ID}}\t{{.Image}}\t{{.Names}}\t{{.Status}}' > "$DEST/docker_ps.txt" 2>/dev/null || true

CONTENT_COMMIT=unknown
if [ -n "$CONTENT_DIR" ] && [ -d "$CONTENT_DIR/.git" ]; then
    CONTENT_COMMIT=$("${GIT[@]}" -C "$CONTENT_DIR" rev-parse HEAD 2>/dev/null || echo unknown)
    {
        echo "commit=$CONTENT_COMMIT"
        echo "dir=$CONTENT_DIR"
        "${GIT[@]}" -C "$CONTENT_DIR" log -1 --format='%H %ci %s' 2>/dev/null || true
    } > "$DEST/content_head.txt"
fi
echo "  контент: ${CONTENT_COMMIT:0:12}"

# ---------------------------------------------------------------------------
# 4. Секреты и конфиги
# ---------------------------------------------------------------------------
log "env и конфиги"
ENV_SAVED=0
if [ -f "$APP_DIR/.env" ]; then
    cp -p "$APP_DIR/.env" "$DEST/app.env"
    ENV_SAVED=1
    echo "  .env -> app.env"
else
    warn "нет $APP_DIR/.env — без него при восстановлении сменятся ADMIN_TOKEN и INDEXNOW_KEY"
fi

mkdir -p "$DEST/proxy"
for d in /etc/caddy /etc/nginx; do
    if [ -d "$d" ]; then
        cp -a "$d" "$DEST/proxy/" && echo "  $d -> proxy/$(basename "$d")/"
    fi
done
# Caddy может жить и контейнером — сохраняем его Caddyfile по месту монтирования.
for c in $(docker ps -q 2>/dev/null); do
    img=$(docker inspect -f '{{.Config.Image}}' "$c" 2>/dev/null || true)
    case "$img" in
        *caddy*)
            name=$(docker inspect -f '{{.Name}}' "$c" 2>/dev/null | tr -d / || true)
            [ -n "$name" ] || continue
            docker inspect "$c" > "$DEST/proxy/container_$name.json" 2>/dev/null || true
            src=$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/etc/caddy/Caddyfile"}}{{.Source}}{{end}}{{end}}' "$c" 2>/dev/null || true)
            if [ -n "$src" ] && [ -f "$src" ] && cp -p "$src" "$DEST/proxy/Caddyfile.$name"; then
                echo "  Caddyfile контейнера $name -> proxy/Caddyfile.$name"
            fi
            ;;
    esac
done
crontab -l -u root > "$DEST/proxy/crontab.root.txt" 2>/dev/null || true
[ -n "${SUDO_USER:-}" ] && { crontab -l -u "$SUDO_USER" > "$DEST/proxy/crontab.$SUDO_USER.txt" 2>/dev/null || true; }

# ---------------------------------------------------------------------------
# 5. Код
# ---------------------------------------------------------------------------
log "код"
# Контент при неудачном клоне деплой кладёт ВНУТРЬ каталога приложения
# (content/ как запасной вариант) — такой каталог в архив кода не берём:
# у него своя история и свой бэкап.
EXCLUDES=(--exclude=./.git --exclude=./tailwind/node_modules)
if [ -n "$CONTENT_DIR" ]; then
    case "$(readlink -f "$CONTENT_DIR")/" in
        "$(readlink -f "$APP_DIR")"/*)
            rel=${CONTENT_DIR#"$APP_DIR"/}
            EXCLUDES+=(--exclude="./$rel")
            ;;
    esac
fi
WORKTREE=0
CURRENT_FILE="$DEST/app_worktree.tar.gz"
rc=0
$LOW tar czf "$CURRENT_FILE" -C "$APP_DIR" "${EXCLUDES[@]}" . || rc=$?
CURRENT_FILE=""
if [ "$rc" -le 1 ]; then                       # 1 = «файл менялся при чтении», не ошибка
    WORKTREE=1
    echo "  рабочее дерево -> app_worktree.tar.gz ($(du -h "$DEST/app_worktree.tar.gz" | cut -f1))"
else
    rm -f "$DEST/app_worktree.tar.gz"
    warn "архив рабочего дерева не получился (tar, код $rc)"
fi

APP_BUNDLE=0
CURRENT_FILE="$DEST/app.bundle"
if $LOW "${GIT[@]}" -C "$APP_DIR" bundle create -q "$CURRENT_FILE" --all 2>/dev/null; then
    APP_BUNDLE=1
    echo "  история -> app.bundle ($(du -h "$CURRENT_FILE" | cut -f1))"
else
    rm -f "$CURRENT_FILE"
    warn "git bundle не получился (не критично: код есть в app_worktree.tar.gz и на GitHub)"
fi
CURRENT_FILE=""

# ---------------------------------------------------------------------------
# 6. Данные
# ---------------------------------------------------------------------------
DB_COPIES=0; DB_FAILED=0; WEB_DATA=0
if [ -n "$CID" ]; then
    log "данные"
    # Базу SQLite в режиме WAL нельзя честно скопировать как файл: часть
    # записей живёт в -wal, и копия «на ходу» может оказаться битой. Backup
    # API SQLite делает согласованный снимок, не мешая сайту писать дальше.
    mkdir -p "$DEST/db"
    docker exec -i "$CID" python - > "$DEST/db/MAP.txt" <<'PY' || { DB_FAILED=$((DB_FAILED + 1)); warn "python в контейнере не отработал — копий баз нет"; }
import glob, os, sqlite3
for src in sorted(glob.glob('/app/data/**/*.db', recursive=True)):
    rel = os.path.relpath(src, '/app/data')
    name = rel.replace('/', '__')
    tmp = '/tmp/dataist_backup__' + name
    try:
        s = sqlite3.connect(src, timeout=30)
        d = sqlite3.connect(tmp)
        s.backup(d)
        ok = d.execute('PRAGMA integrity_check').fetchone()[0]
        tables = [r[0] for r in d.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
        counts = ','.join('%s=%d' % (t, d.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0])
                          for t in tables)
        d.close(); s.close()
        print('\t'.join([rel, name, tmp, ok, counts]))
    except Exception as e:  # noqa: BLE001
        print('\t'.join([rel, name, tmp, 'ERROR: %s' % e, '']))
PY
    while IFS=$'\t' read -r rel name tmp ok counts; do
        [ -n "$rel" ] || continue
        if [ "$ok" = "ok" ] && docker cp "$CID:$tmp" "$DEST/db/$name" >/dev/null 2>&1; then
            DB_COPIES=$((DB_COPIES + 1))
            echo "  $rel -> db/$name (integrity ok; $counts)"
        else
            DB_FAILED=$((DB_FAILED + 1))
            warn "$rel: копия не снята ($ok)"
        fi
        docker exec "$CID" rm -f "$tmp" >/dev/null 2>&1 || true
    done < "$DEST/db/MAP.txt"

    # Весь том — для всего остального (indexnow.json с ключом поисковика,
    # дневные сводки). Код 1 у tar значит «файл менялся, пока читали» — это
    # живая база, её согласованная копия уже лежит в db/.
    CURRENT_FILE="$DEST/web_data.tar.gz"
    rc=0
    docker exec "$CID" nice -n 19 tar czf - -C /app/data . > "$CURRENT_FILE" || rc=$?
    CURRENT_FILE=""
    if [ "$rc" -le 1 ]; then
        WEB_DATA=1
        echo "  том ${DATA_VOLUME} -> web_data.tar.gz ($(du -h "$DEST/web_data.tar.gz" | cut -f1))"
    else
        rm -f "$DEST/web_data.tar.gz"
        warn "tar тома завершился с кодом $rc — архив тома не сохранён"
    fi
fi

# ---------------------------------------------------------------------------
# 7. Образ
# ---------------------------------------------------------------------------
IMAGE_TAGGED=0; IMAGE_SAVED=0
BACKUP_TAG="$BACKUP_IMAGE_REPO:$TS"
if [ -n "$IMAGE_ID" ]; then
    log "образ"
    # Тег — мгновенный откат без пересборки и без лишнего места. Но
    # `docker image prune -a` сносит и помеченные образы, если их не
    # использует ни один контейнер, поэтому рядом кладём ещё и файл.
    docker tag "$IMAGE_ID" "$BACKUP_TAG"
    IMAGE_TAGGED=1
    echo "  $IMAGE_NAME (${IMAGE_ID:7:12}) -> тег $BACKUP_TAG"
    if [ "$WITH_IMAGE" = "1" ]; then
        CURRENT_FILE="$DEST/image.tar.gz"
        if docker save "$BACKUP_TAG" | $LOW gzip -1 > "$CURRENT_FILE"; then
            IMAGE_SAVED=1
            echo "  образ -> image.tar.gz ($(du -h "$DEST/image.tar.gz" | cut -f1))"
        else
            rm -f "$CURRENT_FILE"
            warn "docker save не получился — откат возможен только по тегу $BACKUP_TAG"
        fi
        CURRENT_FILE=""
    fi
    {
        echo "image_name=$IMAGE_NAME"
        echo "image_id=$IMAGE_ID"
        echo "backup_tag=$BACKUP_TAG"
        echo "image_file=$([ "$IMAGE_SAVED" = 1 ] && echo image.tar.gz || echo none)"
    } > "$DEST/image.txt"
fi

# ---------------------------------------------------------------------------
# 8. Контент (по желанию)
# ---------------------------------------------------------------------------
CONTENT_BUNDLE=0
if [ "$WITH_CONTENT" = "1" ] && [ -n "$CONTENT_DIR" ] && [ -d "$CONTENT_DIR/.git" ]; then
    log "контент (WITH_CONTENT=1)"
    CURRENT_FILE="$DEST/content.bundle"
    if $LOW "${GIT[@]}" -C "$CONTENT_DIR" bundle create -q "$CURRENT_FILE" --all; then
        CONTENT_BUNDLE=1
        echo "  контент -> content.bundle ($(du -h "$CURRENT_FILE" | cut -f1))"
    else
        rm -f "$CURRENT_FILE"
        warn "бандл контента не получился"
    fi
    CURRENT_FILE=""
fi

# ---------------------------------------------------------------------------
# 9. Итог — честный: что есть и чего нет
# ---------------------------------------------------------------------------
MISSING=()
[ "$ENV_SAVED" = 1 ]        || MISSING+=(".env")
[ "$APP_COMMIT" != unknown ] || MISSING+=("коммит приложения")
[ "$WORKTREE" = 1 ]         || MISSING+=("рабочее дерево кода")
if [ -n "$CID" ]; then
    [ "$IMAGE_TAGGED" = 1 ] || MISSING+=("образ")
    [ "$WEB_DATA" = 1 ]     || MISSING+=("том данных")
    [ "$DB_FAILED" = 0 ]    || MISSING+=("копии баз ($DB_FAILED)")
else
    MISSING+=("работающий контейнер (образ и данные не сняты)")
fi
KIND=full; [ "${#MISSING[@]}" -eq 0 ] || KIND=partial

{
    echo "kind=$KIND"
    echo "created=$TS"
    echo "app_dir=$APP_DIR"
    echo "compose_project=$PROJECT"
    echo "app_commit=$APP_COMMIT"
    echo "app_branch=$APP_BRANCH"
    echo "app_bundle=$APP_BUNDLE"
    echo "env_saved=$ENV_SAVED"
    echo "image_name=$IMAGE_NAME"
    echo "image_id=$IMAGE_ID"
    echo "image_backup_tag=$([ "$IMAGE_TAGGED" = 1 ] && echo "$BACKUP_TAG")"
    echo "image_saved=$IMAGE_SAVED"
    echo "data_volume=$DATA_VOLUME"
    echo "db_copies=$DB_COPIES"
    echo "web_data_saved=$WEB_DATA"
    echo "content_dir=$CONTENT_DIR"
    echo "content_commit=$CONTENT_COMMIT"
    echo "content_bundle=$CONTENT_BUNDLE"
    echo "missing=${MISSING[*]:-}"
} > "$DEST/SNAPSHOT.txt"
( cd "$DEST" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt )
chmod -R go-rwx "$DEST"

echo ""
echo "=== Снапшот: $DEST  ($(du -sh "$DEST" | cut -f1))"
echo "  тип: $KIND"
if [ "$KIND" = full ]; then
    echo "  всё на месте: код, .env, образ, данные, состояние контента"
else
    echo "  НЕ СОХРАНЕНО: ${MISSING[*]}" >&2
fi
echo ""
echo "Откат к этому снапшоту:   sudo bash restore_web.sh $DEST"
echo "  (с данными аналитики:   sudo bash restore_web.sh $DEST --with-data)"
echo ""
echo "Снапшот лежит на том же диске, что и сайт. Чтобы он пережил и поломку VM,"
echo "заберите копию к себе:"
echo "  на VM:        sudo tar cf /tmp/web_$TS.tar -C $BACKUP_ROOT web_$TS && sudo chown \$USER /tmp/web_$TS.tar"
echo "  у себя:       gcloud compute scp <имя-VM>:/tmp/web_$TS.tar . --zone <зона>"
echo "  на VM потом:  rm /tmp/web_$TS.tar"

[ "$KIND" = full ] || exit 1

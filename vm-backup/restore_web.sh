#!/usr/bin/env bash
# restore_web.sh — откат сайта dataist.ai к снапшоту backup_web.sh.
#
#   sudo bash restore_web.sh /opt/dataist_backups/web_<timestamp>
#       вернуть код, .env и образ — то, что ломает неудачный деплой.
#   sudo bash restore_web.sh /opt/dataist_backups/web_<timestamp> --with-data
#       и ещё данные сайта (аналитика, indexnow.json) — только если испорчены
#       именно они: всё, что сайт записал после снапшота, откатится вместе с ними.
#   --yes   не спрашивать подтверждение (для запуска без терминала)
#
# Ничего не выбрасывается молча: ПЕРЕД откатом текущее состояние (образ,
# .env, рабочее дерево, а с --with-data и данные) сохраняется в
# <снапшот>/pre-restore_<время>/ — значит, и сам откат можно откатить.
#
# Статьи скрипт не трогает: сайт сам каждую минуту зеркалит их из GitHub,
# и любая правка на диске исчезла бы через минуту. Откат статей — на GitHub.
set -euo pipefail

SNAP=""; WITH_DATA=0; ASSUME_YES=0
for a in "$@"; do
    case "$a" in
        --with-data) WITH_DATA=1 ;;
        --yes|-y)    ASSUME_YES=1 ;;
        -*)          echo "неизвестный ключ: $a" >&2; exit 2 ;;
        *)           SNAP=$a ;;
    esac
done
[ -n "$SNAP" ] || { echo "Использование: sudo bash $0 /opt/dataist_backups/web_<timestamp> [--with-data] [--yes]" >&2; exit 2; }
[ "$(id -u)" -eq 0 ] || { echo "Запустите от root: sudo bash $0 ..." >&2; exit 1; }
SNAP=$(readlink -f "$SNAP")
[ -f "$SNAP/SNAPSHOT.txt" ] || { echo "нет $SNAP/SNAPSHOT.txt — это не снапшот backup_web.sh" >&2; exit 1; }

val() { grep -m1 "^$1=" "$SNAP/SNAPSHOT.txt" | cut -d= -f2- || true; }
KIND=$(val kind)
if [ "$KIND" = interrupted ] || [ "$KIND" = failed ]; then
    echo "Снапшот не был завершён (kind=$KIND) — восстанавливаться из него нельзя." >&2
    exit 1
fi
APP_DIR=$(val app_dir)
PROJECT=$(val compose_project)
APP_COMMIT=$(val app_commit)
APP_BRANCH=$(val app_branch)
IMAGE_NAME=$(val image_name)
BACKUP_TAG=$(val image_backup_tag)
DATA_VOLUME=$(val data_volume)
CREATED=$(val created)

GIT=(git -c "safe.directory=*")
if docker compose version >/dev/null 2>&1; then DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then DC="docker-compose"
else echo "нет docker compose" >&2; exit 1; fi

# Контрольные суммы — до любых действий: откат из битого архива хуже, чем никакой.
if [ -f "$SNAP/SHA256SUMS.txt" ]; then
    if ! ( cd "$SNAP" && sha256sum --quiet -c SHA256SUMS.txt ); then
        echo "Контрольные суммы снапшота НЕ сходятся — файлы повреждены. Откат отменён." >&2
        exit 1
    fi
fi

[ -d "$APP_DIR" ] || { echo "нет каталога приложения $APP_DIR" >&2; exit 1; }
[ -n "$IMAGE_NAME" ] && [ -n "$BACKUP_TAG" ] || { echo "в снапшоте нет образа — откатывать нечего (kind=$KIND)" >&2; exit 1; }
if [ "$WITH_DATA" = 1 ] && { [ -z "$DATA_VOLUME" ] || [ ! -f "$SNAP/web_data.tar.gz" ]; }; then
    echo "в снапшоте нет данных — --with-data невозможен" >&2; exit 1
fi

echo "=== Откат сайта к снапшоту $CREATED"
echo "  приложение : $APP_DIR (compose-проект $PROJECT)"
echo "  код        : $APP_BRANCH @ ${APP_COMMIT:0:12}"
echo "  образ      : $BACKUP_TAG -> $IMAGE_NAME"
echo "  данные     : $([ "$WITH_DATA" = 1 ] && echo "ОТКАТЫВАЮТСЯ (том $DATA_VOLUME)" || echo "не трогаются")"
if [ "$ASSUME_YES" != 1 ]; then
    if [ ! -t 0 ]; then echo "Нет терминала для подтверждения — добавьте --yes" >&2; exit 1; fi
    read -r -p "Продолжить? Сайт перезапустится и до ~1 минуты будет недоступен, как при деплое [y/N] " ans
    case "$ans" in y|Y|yes|да|Да) ;; *) echo "отменено"; exit 1 ;; esac
fi

# ---------------------------------------------------------------------------
# 1. Образ из снапшота должен быть под рукой ДО того, как что-то менять
# ---------------------------------------------------------------------------
if ! docker image inspect "$BACKUP_TAG" >/dev/null 2>&1; then
    if [ -f "$SNAP/image.tar.gz" ]; then
        echo "--- тег $BACKUP_TAG пропал (prune?) — загружаю образ из image.tar.gz"
        gunzip -c "$SNAP/image.tar.gz" | docker load
    fi
fi
docker image inspect "$BACKUP_TAG" >/dev/null 2>&1 \
    || { echo "образа $BACKUP_TAG нет ни тегом, ни файлом — откат невозможен" >&2; exit 1; }

# ---------------------------------------------------------------------------
# 2. Страховка: текущее состояние — рядом со снапшотом
# ---------------------------------------------------------------------------
NOW=$(date +%Y%m%d_%H%M%S)
PRE="$SNAP/pre-restore_$NOW"
mkdir -p "$PRE"; chmod 700 "$PRE"
echo "--- страховка текущего состояния -> $PRE"
CUR_CID=$(cd "$APP_DIR" && $DC -p "$PROJECT" ps -q web 2>/dev/null | head -1 || true)
if [ -n "$CUR_CID" ]; then
    CUR_IMAGE=$(docker inspect -f '{{.Image}}' "$CUR_CID")
    docker tag "$CUR_IMAGE" "dataist-web-prerestore:$NOW"
    echo "  текущий образ -> тег dataist-web-prerestore:$NOW"
fi
[ -f "$APP_DIR/.env" ] && cp -p "$APP_DIR/.env" "$PRE/app.env"
{
    echo "commit=$("${GIT[@]}" -C "$APP_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
    echo "branch=$("${GIT[@]}" -C "$APP_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
    "${GIT[@]}" -C "$APP_DIR" status --porcelain 2>/dev/null || true
} > "$PRE/app_head.txt"
EXCLUDES=(--exclude=./.git --exclude=./tailwind/node_modules)
[ -d "$APP_DIR/content/.git" ] && EXCLUDES+=(--exclude=./content)   # контент со своей историей
tar czf "$PRE/app_worktree.tar.gz" -C "$APP_DIR" "${EXCLUDES[@]}" .
echo "  .env, код -> $(basename "$PRE")/"

# ---------------------------------------------------------------------------
# 3. Код и .env
# ---------------------------------------------------------------------------
echo "--- код: $APP_BRANCH @ ${APP_COMMIT:0:12}"
if ! "${GIT[@]}" -C "$APP_DIR" cat-file -e "$APP_COMMIT^{commit}" 2>/dev/null && [ -f "$SNAP/app.bundle" ]; then
    "${GIT[@]}" -C "$APP_DIR" fetch -q "$SNAP/app.bundle" "+refs/heads/*:refs/remotes/backup-$CREATED/*"
fi
if "${GIT[@]}" -C "$APP_DIR" cat-file -e "$APP_COMMIT^{commit}" 2>/dev/null; then
    if [ "$APP_BRANCH" != unknown ] && [ "$APP_BRANCH" != HEAD ]; then
        "${GIT[@]}" -C "$APP_DIR" checkout -q -f "$APP_BRANCH" 2>/dev/null || true
    fi
    "${GIT[@]}" -C "$APP_DIR" reset -q --hard "$APP_COMMIT"
else
    echo "  коммита $APP_COMMIT нет — восстанавливаю дерево только из архива" >&2
fi
# Поверх — файлы ровно как они лежали на VM, включая правки, которых нет в git.
tar xzf "$SNAP/app_worktree.tar.gz" -C "$APP_DIR"
[ -f "$SNAP/app.env" ] && cp -p "$SNAP/app.env" "$APP_DIR/.env" && echo "  .env восстановлен"

# ---------------------------------------------------------------------------
# 4. Данные (только по --with-data)
# ---------------------------------------------------------------------------
if [ "$WITH_DATA" = 1 ]; then
    echo "--- данные: останавливаю сайт на время подмены тома"
    (cd "$APP_DIR" && $DC -p "$PROJECT" stop web)
    # Страховка текущих данных — уже на остановленном сайте, чтобы и она была
    # согласованной. Том читает временный контейнер из образа снапшота: в нём
    # есть tar, и не нужно тянуть из сети что-то ещё.
    docker run --rm -v "$DATA_VOLUME":/data:ro --entrypoint tar "$BACKUP_TAG" czf - -C /data . \
        > "$PRE/web_data.tar.gz"
    echo "  текущие данные -> $(basename "$PRE")/web_data.tar.gz"
    # Сначала весь том из архива, затем поверх — согласованные копии баз.
    # У копии базы своя история, поэтому чужие -wal/-shm рядом с ней удаляются:
    # SQLite иначе «доиграл» бы в старую базу журнал новой и испортил её.
    docker run --rm -v "$DATA_VOLUME":/data -v "$SNAP":/snap:ro --entrypoint sh "$BACKUP_TAG" -c '
        set -e
        find /data -mindepth 1 -delete
        tar xzf /snap/web_data.tar.gz -C /data
        if [ -f /snap/db/MAP.txt ]; then
            while IFS="$(printf "\t")" read -r rel name tmp ok counts; do
                [ -n "$rel" ] && [ "$ok" = ok ] && [ -f "/snap/db/$name" ] || continue
                rm -f "/data/$rel-wal" "/data/$rel-shm"
                cp "/snap/db/$name" "/data/$rel"
                echo "  база $rel восстановлена ($counts)"
            done < /snap/db/MAP.txt
        fi'
fi

# ---------------------------------------------------------------------------
# 5. Запуск из образа снапшота
# ---------------------------------------------------------------------------
echo "--- запуск: $IMAGE_NAME <- $BACKUP_TAG"
docker tag "$BACKUP_TAG" "$IMAGE_NAME"
(cd "$APP_DIR" && $DC -p "$PROJECT" up -d --no-build --force-recreate web)

NEW_CID=$(cd "$APP_DIR" && $DC -p "$PROJECT" ps -q web | head -1)
PORT=$(docker port "$NEW_CID" 8080/tcp 2>/dev/null | head -1 | awk -F: '{print $NF}')
WANT_IMAGE=$(docker image inspect -f '{{.Id}}' "$BACKUP_TAG")
GOT_IMAGE=$(docker inspect -f '{{.Image}}' "$NEW_CID")
health=""
deadline=$((SECONDS + ${RESTORE_HEALTH_TIMEOUT:-180}))
while (( SECONDS < deadline )); do
    health=$(curl -fsS --max-time 5 "http://127.0.0.1:${PORT:-8089}/api/v1/admin/health" 2>/dev/null) && break
    health=""
    sleep 2
done

echo ""
if [ -n "$health" ] && [ "$WANT_IMAGE" = "$GOT_IMAGE" ]; then
    echo "=== Откат выполнен: сайт отвечает, работает образ из снапшота"
    echo "  $health"
else
    echo "=== ВНИМАНИЕ: сайт не подтвердил готовность за отведённое время" >&2
    echo "  образ: ожидался ${WANT_IMAGE:7:12}, работает ${GOT_IMAGE:7:12}" >&2
    echo "  логи: cd $APP_DIR && sudo $DC -p $PROJECT logs --tail=80 web" >&2
fi
echo ""
echo "Отменить этот откат (вернуть то, что было до него):"
echo "  образ  : sudo docker tag dataist-web-prerestore:$NOW $IMAGE_NAME && (cd $APP_DIR && sudo $DC -p $PROJECT up -d --no-build --force-recreate web)"
echo "  .env   : sudo cp $PRE/app.env $APP_DIR/.env"
echo "  код    : см. $PRE/app_head.txt и $PRE/app_worktree.tar.gz"
[ "$WITH_DATA" = 1 ] && echo "  данные : архив $PRE/web_data.tar.gz"
echo ""
echo "Следующий деплой (scripts/deploy_web.sh) снова соберёт код с ветки на GitHub —"
echo "если откатывались из-за неудачного кода, сначала верните ветку."
echo "Статьи откатываются на GitHub, а не здесь: снимок контента — $(val content_commit)"
[ -n "$health" ] && [ "$WANT_IMAGE" = "$GOT_IMAGE" ]

# shallowsea 정적 웹 페이지 (devlog 007). web/data/는 scripts/build_site_data.py로 먼저 만든다.
FROM nginx:1.27.3-alpine
ARG VERSION=dev
ARG COMMIT=unknown
LABEL org.opencontainers.image.title="shallowsea" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${COMMIT}"
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY web/ /usr/share/nginx/html/
RUN cd /usr/share/nginx/html \
 && test -f data/summary.json && test "$(ls data/dem | wc -l)" = 109 \
 && find . -type f \( -name '*.bin' -o -name '*.json' -o -name '*.js' -o -name '*.css' -o -name '*.html' \) -exec gzip -9 -k {} \; \
 && printf '{"status":"ok","version":"%s","commit":"%s"}\n' "$VERSION" "$COMMIT" > healthz.json \
 && chmod -R a+rX /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz >/dev/null || exit 1

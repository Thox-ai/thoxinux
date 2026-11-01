#!/bin/bash
set -e
cd ~/w5-e-runtime
docker build -f Dockerfile.userspace -t thoxos-g/userspace-agentos:0.1.0-w5e . > build-userspace.log 2>&1
docker save -o userspace-agentos.tar thoxos-g/userspace-agentos:0.1.0-w5e
docker run --rm -v $HOME/w5-e-runtime/seed:/seed --entrypoint bash thoxos-g/demo:0.1.0 -c 'chmod -R u+w /seed/registry 2>/dev/null; rm -rf /seed/registry' || true
docker rm -f w5e-seed-reg >/dev/null 2>&1 || true
docker run -d --name w5e-seed-reg -v $HOME/w5-e-runtime/seed:/seed -p 127.0.0.1:5000:5000 --entrypoint registry thoxos-g/demo:0.1.0 serve /seed/registry-seed.yml >/dev/null
for i in $(seq 1 30); do curl -fs http://127.0.0.1:5000/v2/ >/dev/null 2>&1 && break; sleep 0.5; done
skopeo copy --format oci --dest-compress-format gzip --dest-tls-verify=false docker-archive:$HOME/w5-e-runtime/userspace-agentos.tar docker://127.0.0.1:5000/thoxos/userspace:0.1.0 >> build-userspace.log 2>&1
skopeo inspect --tls-verify=false --raw docker://127.0.0.1:5000/thoxos/userspace:0.1.0 > seed/manifest.json
docker rm -f w5e-seed-reg >/dev/null
rm -rf democtx; mkdir democtx; cp -a seed democtx/; cp variant/Dockerfile.demo democtx/Dockerfile
docker build -t thoxos-g/demo-agentos:0.1.0-w5e democtx >> build-userspace.log 2>&1
echo BUILD_VARIANT_OK

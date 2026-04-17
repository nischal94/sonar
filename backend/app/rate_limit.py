from slowapi import Limiter
from slowapi.util import get_remote_address

# get_remote_address reads request.client.host — the direct socket peer.
# Behind a reverse proxy / load balancer / ingress, that becomes the proxy's
# IP and the per-IP limit collapses into a global limit for every user
# behind that proxy. Prod deploys MUST run uvicorn with --proxy-headers and
# --forwarded-allow-ips=<proxy-subnet> before this limiter is trustworthy.
# Tracked: https://github.com/nischal94/sonar/issues/62
limiter = Limiter(key_func=get_remote_address)

# Built with app/ as its context, not proxy/, because the image needs both the nginx
# config and the static front end and those are siblings. `dockerfile:` in compose names
# this file; `.dockerignore` at app/ keeps the wider context from carrying anything else.
#
# The front end is COPYed rather than bind-mounted. Two reasons: a bind mount needs an
# SELinux :z label on the development machine and fails as a bare permission error without
# one, and a COPY is what makes the image self-contained on a machine that has never seen
# this repository — the scenario §6 grades.
FROM nginx:1.27-alpine

COPY proxy/upto.conf /etc/nginx/conf.d/default.conf
COPY web /usr/share/nginx/html

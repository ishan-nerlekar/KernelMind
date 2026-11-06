**What the instruction requires**
> And have this data then be pushed to a webserver running on port 8080

i.e. whatever is pushed gets deployed.

**What passes today**
`near-4-hardcoded/solve.sh` (below) installs a hook whose whole body is `echo "hello world" > /var/www/html/hello.html`. It never deploys the pushed content, and it passes.

**Why the tests miss it**
`verify.sh` pushes exactly the instruction's example (`echo 'hello world' > hello.html`) and checks for exactly `hello world`. Open PR #39 rewrites this verifier's auth, but its new `verify.sh` still pushes and checks `hello world`, so the gap remains with it merged.

**Suggested fix:** push content the agent can't predict and check that it is served, e.g.
```bash
TOKEN="deploy-$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"
echo "$TOKEN" > hello.html   # instead of 'hello world'
...
[ "$(curl -s http://localhost:8080/hello.html)" = "$TOKEN" ]
```
A second push with different content would also catch hooks that deploy only once.
Not run locally (the verifier needs the full ssh/nginx setup); the reasoning is above.

Confirmed with Harbor 0.25 (`harbor trial start -a oracle`): the reference and each solution below score reward 1.0.

**Reproduce** (Harbor oracle agent with the solution swapped in):
```bash
cp -R configure-git-webserver /tmp/configure-git-webserver-check
# put one of the solve.sh scripts below in /tmp/configure-git-webserver-check/solution/solve.sh, then:
harbor trial start -p /tmp/configure-git-webserver-check -a oracle
```

<details><summary><code>near-4-hardcoded/solve.sh</code> (passes the current tests)</summary>

```bash
#!/bin/bash
set -e
DEBIAN_FRONTEND=noninteractive apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y git nginx openssh-server
adduser --disabled-password --gecos '' --shell /bin/bash --home /home/git git
echo 'git:password' | chpasswd
mkdir -p /home/git/.ssh && touch /home/git/.ssh/authorized_keys
chmod 700 /home/git/.ssh && chmod 600 /home/git/.ssh/authorized_keys
chown -R git:git /home/git/.ssh
mkdir -p /git/server && chown -R git:git /git
su - git -c 'git init --bare /git/server'
mkdir -p /var/www/html && chown -R git:git /var/www/html
cat > /git/server/hooks/post-receive <<'EOF'
#!/bin/bash
echo "hello world" > /var/www/html/hello.html
EOF
chmod +x /git/server/hooks/post-receive
chown git:git /git/server/hooks/post-receive
cat > /etc/nginx/conf.d/git-site.conf <<'EOF'
server {
    listen 8080;
    server_name localhost;
    root /var/www/html;
    location / {
        try_files $uri $uri/ =404;
    }
}
EOF
rm -f /etc/nginx/sites-enabled/default
service ssh start
service nginx start
```
</details>


_Found while auditing Terminal-Bench 2.0 verifiers with near-miss solutions (commit `2fd12b8`). Happy to turn the suggested test change into a PR._

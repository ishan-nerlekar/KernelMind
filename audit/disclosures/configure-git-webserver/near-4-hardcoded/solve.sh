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

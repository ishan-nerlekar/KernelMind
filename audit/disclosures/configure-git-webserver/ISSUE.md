**Title:** configure-git-webserver: a post-receive hook that ignores the push and writes a literal "hello world" passes

**What the instruction requires**
> And have this data then be pushed to a webserver running on port 8080

i.e. whatever is pushed gets deployed.

**What passes today**
`near-4-hardcoded/solve.sh` installs a hook whose whole body is `echo "hello world" > /var/www/html/hello.html`. It never deploys the pushed content, and it passes.

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

# Environment Build Skill

## Objective

Build a reproducible, runnable Docker environment for a source repository and
write an honest `env/<project>/env-manifest.json`. Success means
`env_status=ready`, `build_exit_code=0`, and a non-empty `image_id` that was
produced by an actual Docker build. Never mark an environment ready when only
files were generated or when the image does not exist.

## Workflow

1. Detect before building:

   ```bash
   bash scripts/env/build_env.sh <SOURCE> --project <NAME> --dry-run
   ```

   Read `env/<project>/env-manifest.json`: languages, install commands,
   limitations, and partial reasons. If detection is wrong, fix the generated
   Dockerfile with `--no-generate` rather than pretending the build succeeded.

2. Choose the smallest mode that can satisfy the task:

   - `none`: only place source in the image.
   - `auto`: Python editable `--no-deps`, Node `--ignore-scripts`, Rust/Go fetch.
   - `requirements`: install Python requirements.
   - `full`: full compile/install; use only when the evaluator needs it.

3. Build:

   ```bash
   bash scripts/env/build_env.sh <SOURCE> --project <NAME> --mode <MODE>
   ```

   Treat exit codes as data: `0=ready`, `10=partial`, `20=blocked`.
   Keep the build log. Do not delete dependencies or tests to force a pass.

4. On failure, read `build.log` and classify the cause:

   - missing system package -> add it to the Dockerfile;
   - wrong language/version -> fix the base image or toolchain;
   - network/private registry -> mark `blocked` with the exact requirement;
   - GPU/CUDA only -> keep the CPU-verifiable part and record the limitation.

5. Verify after a successful build:

   ```bash
   docker run --rm --network none --entrypoint /bin/bash <IMAGE> \
     -lc 'test -d /opt/target && python3 --version 2>/dev/null; node --version 2>/dev/null'
   ```

   `ready` requires the source tree and the expected runtime to be present.

## Rules

- Run every install, compile, and postinstall step inside `docker build`.
- Never write credentials, tokens, or `.env` contents into the Dockerfile,
  manifest, or log.
- Do not use `--privileged`, do not mount `docker.sock`, and do not run target
  code on the host.
- Keep all limitations and partial reasons in the manifest. A truthful
  `partial` or `blocked` is better than a false `ready`.
- If a build needs GPU or an external service, record it as a limitation and
  keep the CPU path reproducible.

## Output

Return a compact result:

```text
project: <name>
image: <image:tag>
env_status: ready|partial|blocked
mode: <mode>
manifest: env/<project>/env-manifest.json
limitations: ...
next: verify-agent
```

The machine-readable contract is `env/<project>/env-manifest.json`; the
evaluator reads `env_status`, `build_exit_code`, `image_id`, `partial_reasons`,
and `limitations` from it.

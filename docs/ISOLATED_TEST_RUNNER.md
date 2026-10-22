# Isolated Repository Test Runner

The API must not execute code from a connected repository directly on its host. The test runner uses a disposable Docker container and copies the checked-out workspace into an ephemeral in-container filesystem.

## Build the runner image

From the repository root:

```bash
docker build -f Dockerfile.test-runner -t openincident-test-runner:local .
```

The image includes Node.js 22, Python 3, Git, and build tools. Add language-specific tooling only when required by supported project types.

## Runtime defaults

- Docker container per command, removed on exit.
- Network disabled by default (`OPENINCIDENT_TEST_RUNNER_NETWORK=none`).
- Source workspace mounted read-only at `/source`.
- Repository copied into an ephemeral `/workspace` tmpfs; changes are discarded after each command.
- Non-root UID/GID 10001, read-only container root filesystem, dropped Linux capabilities, and `no-new-privileges`.
- CPU, memory, process-count, and wall-clock limits; stdout/stderr are truncated in the result.
- Host environment variables and project-configured environment variables are not passed into the container.

Set `OPENINCIDENT_TEST_RUNNER_IMAGE` to select a locally available runner image. Resource defaults can be tuned with `OPENINCIDENT_TEST_RUNNER_MEMORY`, `OPENINCIDENT_TEST_RUNNER_CPUS`, and `OPENINCIDENT_TEST_RUNNER_PIDS`.

## Network policy

Do not enable network access for untrusted code in production without a separate egress-control design. With the default `none` mode, package installation commands that need internet access will fail. If a trusted development workflow explicitly requires Docker bridge networking, `OPENINCIDENT_TEST_RUNNER_NETWORK=bridge` enables it; this is a weaker isolation posture and must not be treated as production-safe egress filtering.

A stronger production design should use an isolated runner service or VM, default-deny egress, allowlisted package mirrors, per-run quotas, and an explicit cleanup/reaper for abandoned jobs. Docker isolation reduces risk but is not a substitute for a hardened VM boundary against hostile multi-tenant workloads.

## API host requirements

- Docker Engine must be installed and running.
- The API process must have permission to call Docker. Access to the Docker daemon is highly privileged; do not expose its socket to the web or agent containers.
- Do not mount production credentials, host home directories, Docker sockets, or production databases into the test container.
- Keep production and test credentials, networks, and databases separate.

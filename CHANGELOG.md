# Changelog

## 0.1.1 (2026-11-02)

- Make the pinned installation usable on macOS by restricting pywin32 to Windows.
- Use Windows short-path aliases for native ZIM libraries when archive paths contain non-ASCII characters, with guidance when aliases are unavailable.
- Add explicit stdio/Streamable HTTP selection while preserving `--stdio` and the existing HTTP default.
- Store World Bank raw downloads beside the selected database, including external database locations.
- Replace machine-specific setup with separate platform, data and client guides for Codex, Claude Code, Open WebUI and other MCP hosts.
- Add synthetic onboarding data and a portable verifier for real stdio/HTTP connections.
- Make the optional skill and WebUI helpers independent of a fixed username, local path and model.
- Add native ZIM and transport regression tests plus CI for Windows, both Mac architectures and Linux.

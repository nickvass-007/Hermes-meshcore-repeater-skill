# Attribution and source provenance

This independent MMTV Mesh project packages the supplied “Hermes MeshCore Repeater Skill — safe rewrite v2.0.0”. The operator confirmed authority to publish that implementation under MIT. No upstream MeshCore, RemoteTerm or Hermes source implementation is bundled.

The initial executable `scripts/repeater_cmd.py`, regression suite, `SKILL.md`, setup reference, example env and original ignore file are preserved byte-for-byte from that supplied bundle. The initial public documentation, test runner, workflow and brand notices wrapped the original package without changing radio execution behaviour. Version 2.0.1 adds a narrowly scoped strict full-public-key reply parser and regression tests; the original bundle remains recoverable from Git history. See the changelog for the exact behaviour change. The repository name differs deliberately from the installed skill name `meshcore-repeater-command`.

## Upstream references

- [MeshCore CLI documentation](https://docs.meshcore.io/cli_commands/)
- [MeshCore CLI implementation](https://github.com/meshcore-dev/MeshCore/blob/main/src/helpers/CommonCLI.cpp)
- [MeshCore repeater implementation](https://github.com/meshcore-dev/MeshCore/blob/main/examples/simple_repeater/MyMesh.cpp)
- [RemoteTerm server control](https://github.com/jkingsman/Remote-Terminal-for-MeshCore/blob/main/app/routers/server_control.py)
- [RemoteTerm contacts](https://github.com/jkingsman/Remote-Terminal-for-MeshCore/blob/main/app/routers/contacts.py)
- [RemoteTerm project](https://github.com/jkingsman/Remote-Terminal-for-MeshCore)
- [Hermes skills documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/)

The supplied reference review date is 2026-11-05. Moving `main` URLs are source references, not pinned compatibility certification. Names and marks belong to their respective owners. This repository is not an official upstream release.

# Pinned OoO mutation source

`Core.scala` is copied without changes from
`examples/ooo-mini/src/main/scala/ooomini/Core.scala` at commit
`4a8757808d344f6db4660ce2e08ae88465f6e27a`.

The fast mutation test uses this file when Git history is absent, for example
in the isolated copy made by `scripts/ci-local.sh` or a shallow checkout.
The test checks the source pin and SHA-256 before it applies each mutation.
When the task pack source changes, update the fixture and both checks together.

# Research artifact storage and recovery

Garden collectors historically kept both raw JSONL traces and compressed copies.
These duplicates accounted for most of this checkout's disk use. The cleanup
utility removes only a raw trace whose original manifest authenticates both
files and whose gzip copy decompresses to exactly the original bytes. It never
deletes the compressed evidence, results, screenshots, models or source archives.

The October 4, 2026 cleanup removed 1,541 redundant files across 23 older
bundles, reclaiming 257.7 GiB (276,741,120,000 allocated bytes). The checkout
fell from about 310 GiB to 52 GiB before the next experiment. Every compressed
copy passed hash and decompression checks; all 23 original manifests stayed
unchanged. The index SHA256 is
`e7c832fb9759ac939492ced8c9f155fed3105e4cf243e109be89cafcff65fa83`.
Seven safety/recovery tests pass. A real archived trace was also restored,
matched to its original checksum and compacted again; that small recovery
check has its own `artifacts/storage-recovery-check-20261004.json` index.

## Restore an older bundle

The local restoration index is `artifacts/storage-compaction-20261004.json`;
the adjacent `storage-compaction-20261004.journal.jsonl` records verified deletion
intents and completion. Preserve both alongside the artifact directories.

```sh
# Restore only the selected bundle, not the entire research archive.
python3 scripts/artifact_storage.py restore \
  artifacts/storage-compaction-20261004.json \
  --bundle garden-landing-second-opening-v1

# A single root-relative filename is also supported.
python3 scripts/artifact_storage.py restore \
  artifacts/storage-compaction-20261004.json \
  --file garden-landing-adult-resources-v1/eligible.jsonl
```

Restoration verifies the original manifest, compressed hash, decompressed hash
and length. It never overwrites a different existing file. It restores bytes,
not original filesystem timestamps or permissions. The index records the
absolute artifact root, so these commands are intended for this checkout.
Allow enough disk space for the chosen bundle; some older bundles exceed 50 GiB.

Original manifests are unchanged. Portable audits and tools that read gzip
continue to work directly. Older *full-bundle* checks that require every original
filename need their bundle restored first. Do not rewrite those manifests to
hide missing raw files. The original day 320 patch-sweep and confirmation
bundles were explicitly excluded from compaction.

## Plan another cleanup

```sh
# Inventory only. Use a fresh index path and protect any active bundle.
python3 scripts/artifact_storage.py plan \
  --out artifacts/storage-next.json \
  --keep garden-landing-active-experiment

# Review the index before this explicit deletion command.
python3 scripts/artifact_storage.py apply artifacts/storage-next.json

python3 scripts/tests/artifact-storage-test.py
```

Only manifest-covered JSONL/gzip pairs in older `garden-landing-*` directories
are eligible. Missing copies, uncovered files and the two protected bundles
are left alone. Symlinks, hardlinked raw files, hash mismatches and changes
during verification stop deletion. The index is persisted before the first
unlink, and each verified intent is flushed before removing that exact file.
An interrupted apply can be rerun with the same index; retained copies are
reverified. Do not run collectors or editors against a bundle being compacted.

## Avoid recreating the duplicates

The day 352 follow-up collector keeps compressed traces only, after checking
their decompressed bytes and persisting the raw hash and length in `run.json`.
Its own manifest describes this compact layout, and its offline verifier
reads gzip directly. Old collectors remain unchanged because their source
hashes are part of frozen experiment provenance. If rerunning them, compact
their completed output explicitly after preserving and reviewing a new index.

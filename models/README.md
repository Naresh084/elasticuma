# Community model profiles

Place reviewed profile files named `*.json` in this directory. ElasticUMA loads
them automatically in addition to the two packaged admitted profiles.

Start from `example.community.json.example`, pin every revision/hash, keep
`verification` set to `community`, and follow [the model compatibility
contract](../docs/models.md).

Do not place weights, tokenizer files, packed model directories, or secrets
here. They belong in the canonical cache outside Git.

# Import a conference attendee list

The target planner needs explicit conference dates and confirmed attendance for
the target and possible intermediaries. Import a permitted organizer roster or
public professional announcements as a JSON manifest. This tool reads a local
file; it does not scrape websites or personal social profiles.

Use the existing person's graph ID when importing a target or connection. A new
attendee does not automatically have relationships in the graph. Attendance
creates no friendship edges and grants no access to private graphs.

## Manifest

The following is a fictitious format example, not evidence of real attendance:

```json
{
  "schema_version": 1,
  "import_id": "organizer-roster",
  "conference": {
    "id": "example-2026",
    "name": "Example Conference",
    "starts": "2026-11-10",
    "ends": "2026-11-12"
  },
  "attendees": [
    {
      "person_id": "existing-target-id",
      "name": "Example Speaker",
      "basis": "public_professional",
      "confirmed": true,
      "source": {
        "url": "https://example.org/speakers",
        "claim": "Example Speaker is confirmed for Example Conference.",
        "observed_at": "2026-10-24"
      }
    }
  ]
}
```

`basis` is `public_professional` or `opted_in`; it records the basis supplied by
the importer rather than independently proving consent. Every confirmed record
needs a public HTTP(S) source and a professional claim. Personal social-profile
sources are excluded. Keep owner tokens, provider keys, private relationships,
email addresses and unrelated personal information out of the manifest.

Existing names must match; new people require a name and are created without
private-graph consent. Dates use `YYYY-MM-DD`; the end cannot precede the start.
Unknown fields, duplicate records, conflicting graph identities and another
importer's attendance ownership are rejected before writing.

## Preview and import in Docker

Stop the demo server before importing into its graph namespace. Set
`ATTENDEE_MANIFEST` to the path of your local JSON file. From the repository
root, preview against the local Compose graph:

```sh
docker compose run --rm -v "$ATTENDEE_MANIFEST:/input/attendees.json:ro" web python -m warmopen.cli import-attendees /input/attendees.json --check
```

The preview validates the whole manifest and checks graph conflicts without
writing. To import, repeat the command without `--check`. Output contains counts,
not the roster or source claims. Start the server again after the import. See the
[runbook](RUNBOOK.md) for the full sequence.

Each manifest is a complete snapshot for its `import_id` and conference. Reusing
that pair updates its attendance facts. Omitting a previously imported person or
setting `confirmed` to `false` withdraws only attendance owned by that import.
People and evidence nodes remain; unrelated attendance, consent, credentials and
relationships remain unchanged. Keep the same import ID for updates to a roster.

Validation happens before writes, but importing uses multiple database queries.
A database interruption can leave a partial snapshot. Restore the connection,
preview again, and reimport the complete manifest before starting the server.

For future planning, import a separate manifest for each future conference with
confirmed target attendance and attending connections. Dates must actually be in
the future when the app runs; a past demo fixture is not a future event.

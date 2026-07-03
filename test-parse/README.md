# test-parse

This directory stores sample outputs, reference logs, and compatibility entrypoints
for the WebRTC parsing tools.

Canonical source scripts live in `/src`:

- `src/decrypt_session_pipeline.py`
- `src/export_sctp_plaintext.py`
- `src/red_vp8_extract.py`
- `src/webrtc_h264_extractor.py`

The same filenames kept in this directory are thin wrappers so older commands such as
`python3 test-parse/decrypt_session_pipeline.py ...` continue to work.

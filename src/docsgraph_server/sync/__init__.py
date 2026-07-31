"""Sync protocol scaffold.

docsgraph-server is the source of truth for synchronized state, stored in
PostgreSQL. Each client (the `docsgraph` local-first app) keeps a local
SQLite copy plus an ordered changelog of operations it has made offline.

The contract:

1. **Push**: the client sends an ordered batch of local ops it has made
   since its last known cursor (`SyncPushRequest`). The server assigns each
   op a global, monotonically increasing sequence number, applies the ops
   to Postgres inside a transaction, and acknowledges each op with the
   sequence number it was assigned.
2. **Pull**: the client asks for any ops with a sequence number greater
   than the highest one it has already seen (its cursor). The server
   returns those ops — which may originate from other clients/users — plus
   an updated cursor value for the client to persist (`SyncPullResponse`).

This module currently only scaffolds the interface (pydantic models +
route stubs in `sync/router.py`); the actual reconciliation logic
(sequence allocation, conflict handling, persistence) is not implemented
yet.
"""

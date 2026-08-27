# Gunicorn config - auto-loaded from the repo root, so it applies even when the
# host runs the default `gunicorn app:app`.
#
# The report analysis takes longer than gunicorn's 30s default on small CPUs,
# so raise the worker timeout. One worker keeps memory low; the reader now
# streams rows, so RAM stays flat.

timeout = 180
workers = 1
threads = 4

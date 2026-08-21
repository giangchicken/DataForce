"""The only package that reads `config/`, and the only one that knows a path.

Everything under `modalities/`, `profiles/`, `pipeline/` and `core/` is the engine:
it computes, and it never opens a file. That is what lets a web handler, a notebook or
another codebase import it from any working directory. Turning the committed policy
into the objects the engine accepts is this package's whole job.

Every function here takes the location it reads as a required argument. There is no
module-level default and nothing infers a path from the current directory -- the
inference is exactly what made the library work only from the repository root.
"""

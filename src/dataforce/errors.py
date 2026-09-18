"""shape · ConfigError -- a declaration that is wrong or missing, raised before any record is read.

Everything that goes wrong *about* a single record is a value on that record instead
(§ *Error Behavior*), which is why this file holds one exception and not a hierarchy.

There is a second one, and it is the case that rule does not cover: `StepNotRun`, in
`modalities/text2text/dataset_management/`. It is not something that went wrong about a record --
it is a record that may not become one, so there is no record for the answer to be a value on. It
lives with the precondition that raises it rather than here, because what it refuses on is one
modality's shape and one law's obligation, and neither is this package's.
"""


class ConfigError(Exception):
    """A declaration is wrong or missing, and no record has been read yet."""

"""LOGIC · the document one vector is taken over, and the name of the model that takes it.

Three things, and they are one concern: *which* model, *what* it is shown, and the signature the
edge hands over so this module never calls it. Splitting them off ``modality.py`` left that module
the four protocol members and the turn behind them; what is here is the whole of the embedding
choice, which is the half a measurement moves.

**The vector is only as reproducible as the endpoint the edge resolved**, which is the limit
Requirement 23 states. What this module can promise is the *document* -- the conversation less the
excluded roles, in order, joined one way -- and that half is a pure function of the parts, which is
what makes it assertable against a stand-in encoder that reveals its input.

**``exclude_roles`` is a measured choice and the manifest records what re-measures it.** It is read
here rather than assigned in a class body (I5), and it is a declaration rather than a constant
because which roles carry no signal is a fact about a corpus: the instruction turn is identical
across every record of this one, so embedding it moves every vector the same distance and buys
nothing.
"""

from collections.abc import Callable, Container, Sequence

from dataforce.declarations import declared_name, declared_roles
from dataforce.manifest import Manifest
from dataforce.record import Part

# What turns one document into one vector. The model behind it is an endpoint `edge/bootstrap.py`
# resolves and hands over, because the engine opens no file and reaches no service (I1) -- the same
# shape Requirement 16 gives a media modality's URI resolver, "declared when it is built".
type Encoder = Callable[[str], Sequence[float]]

# What this modality's own manifest declares about its vectors.
EMBEDDING = "embedding"
MODEL = "model"
EXCLUDE_ROLES = "exclude_roles"

# What separates one turn from the next in the document a vector is taken over.
TURN_SEPARATOR = "\n\n"


def embedding_model(manifest: Manifest) -> str:
    """Which model this modality's vectors come from, by the name its deployment serves it under.

    Read here rather than at the edge because the implementation that needs a key is the one that
    knows what it means (`manifest.py`), and resolved there rather than here because resolving it
    opens `config/model/<model>.json` (I1). `edge/bootstrap.py` calls this, builds the `Encoder`,
    and hands it over.
    """
    return declared_name(manifest, EMBEDDING, MODEL)


def roles_not_embedded(manifest: Manifest) -> frozenset[str]:
    """The roles the manifest leaves out of the document a vector is taken over."""
    return declared_roles(manifest, EMBEDDING, EXCLUDE_ROLES)


def embedded_document(parts: Sequence[Part], not_embedded: Container[str]) -> str:
    """The conversation less the excluded roles, in order, as one string.

    The half of `embedding` that is a pure function of the parts, and the whole of what this module
    can promise: the vector itself is only as reproducible as the endpoint the edge resolved.
    """
    return TURN_SEPARATOR.join(
        part.text or "" for part in parts if part.role not in not_embedded
    )

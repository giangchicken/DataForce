"""façade · the text2text modality; the object a composition root registers, and the encoder it is built with.

What a composition root needs to register this modality, and nothing else: the implementation, the
encoder signature it is built with, and the manifest key that names the model behind one. The two
shapes in `schema.py` are deliberately not re-exported -- a stage reads a `Detector` structurally
because `pipeline/` may not import this package at all (I2), and re-exporting them would only make
that import look permitted.

The modules beside `schema.py` are named for what they produce -- `turns.py`, `detectors.py`,
`modality.py` -- and none of them is a name anything above this line needs.
"""

from dataforce.modalities.text2text.modality import Encoder, Text2Text, embedding_model

__all__ = ["Encoder", "Text2Text", "embedding_model"]

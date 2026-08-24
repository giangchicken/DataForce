"""DEFINITION · QuestionStore -- what the engine demands of the edge.

One port, because a port with no adapter is a guess about a future caller (P20). The abstraction
belongs to the layer that consumes it, so it is declared here and implemented in ``edge/store/``
(P18).

**Not everything the engine demands of the edge is a port, and this module is not the list.** Since
T12 an axis implementation is *built with* what only the edge can produce -- ``text2text`` with the
encoder behind its static model, ``tool_decision`` with the question template out of
``config/prompts/`` -- and those are constructor arguments handed over by ``edge/bootstrap.py``, not
interfaces anything implements. A port is what the engine calls *back* into during a run; what it is
constructed with is a value. The distinction is why neither of them is declared here.
"""

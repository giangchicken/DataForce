"""DEFINITION · QuestionStore -- what the engine demands of the edge.

One port, because a port with no adapter is a guess about a future caller (P20). The abstraction
belongs to the layer that consumes it, so it is declared here and implemented in ``edge/store/``
(P18).
"""

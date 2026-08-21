"""What the flow is written against: the record, the errors, the gate engine,
the artifacts.

Named for what it holds and not for who imports it. Under the previous name --
`shared/` -- this docstring said "what every stage uses", which names consumers, and
a name that names consumers can admit anything and reject nothing. It admitted a
registry with one caller and an artifacts package with none. The test is answerable
now: a module belongs here when the flow needs it whatever the modality and whatever
the profile.
"""

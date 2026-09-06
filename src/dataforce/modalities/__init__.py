"""facade · one package per modality: what a sample of that kind goes through.

`text2text` is the only one built. The name is the family a sample belongs to — `image2text` and
`video2text` are the next two — and each holds its own parts, its own shapes and nothing shared
with another, because what a check means depends on the kind of thing being checked.
"""

"""LOGIC · the human-review part for this profile: the tool call that ships."""

from dataforce.modalities.text2text.human_review import DecisionLogic


class Decision(DecisionLogic):
    """Which tool call ships, out of what the annotators answered."""

    def decide(self, evidence):
        pass

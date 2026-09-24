"""Deterministic dialogue adapter. Consumes ONLY the agent's bounded context."""


class DeterministicDialogueEngine:
    def generate(self, context: dict, choice_id: str) -> str:
        identity = context["identity"]
        belief = next(
            (
                item
                for item in context["beliefs"]["nodes"]
                if item["node_id"] == "NODE_07"
            ),
            None,
        )
        player_claimed_observation = any(
            "PLAYER_1 said: He observado la señal." in memory
            for memory in context["memory"]
        )

        if choice_id == "ASK_IDENTITY":
            if context.get("resident"):
                resident = context["resident"]
                return (f"Soy {identity['name']}. Trabajo o participo aquí como "
                        f"{resident['role'].lower()}. "
                        f"Mi objetivo es: {resident['public_objective']}")
            return (
                f"Puedes llamarme {identity['name']}. "
                "¿Qué necesitas saber?"
            )

        if choice_id == "ASK_SIGNAL":
            if belief is None:
                if player_claimed_observation:
                    return (
                        "Recuerdo que dijiste haber observado esa señal, "
                        "pero yo todavía no puedo confirmarla."
                    )
                return "No tengo información suficiente sobre esa señal."

            if belief["source"] in {
                "DIRECT_PERCEPTION",
                "ACTIVE_INVESTIGATION",
            }:
                return (
                    "He examinado esa señal personalmente. "
                    "Su comportamiento merece atención."
                )

            if player_claimed_observation:
                return (
                    "He recibido información sobre esa señal y recuerdo "
                    "que dijiste haberla observado, pero necesito contrastarla."
                )
            return (
                "He recibido información sobre esa señal, "
                "pero todavía tendría que contrastarla."
            )

        if choice_id == "TELL_OBSERVED":
            if player_claimed_observation:
                return (
                    "Recuerdo que ya me lo dijiste. Sigue siendo tu "
                    "testimonio, no una observación mía."
                )
            return (
                "Entiendo. Tendré en cuenta tu testimonio, "
                "pero necesito contrastarlo por mi cuenta."
            )

        raise ValueError("UNKNOWN_DIALOGUE_CHOICE")

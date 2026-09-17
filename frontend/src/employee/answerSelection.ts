export function isSingleAnswer(question: {
  mechanic: string;
  prompt_payload: Record<string, unknown>;
}) {
  return (
    question.mechanic === "single_choice" ||
    (question.mechanic === "recognition" && question.prompt_payload.selection_mode === "single")
  );
}

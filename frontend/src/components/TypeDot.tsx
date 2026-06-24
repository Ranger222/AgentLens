import { prettyType, typeColorVar } from "../util";

export function TypeDot({ type }: { type: string }) {
  return (
    <span
      className="type-dot"
      style={{ background: typeColorVar(type) }}
      title={prettyType(type)}
    />
  );
}

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { LabelledOption } from "@/lib/labels";

/** Radix Select treats "" as "no value", so an empty option needs a stand-in. */
const EMPTY = "__empty";

/**
 * A select over labelled options where "" is a real choice ("All statuses",
 * "Any region"). Pair it with a `Label` whose `htmlFor` is `id`, or give it an
 * `ariaLabel` when it stands alone in a toolbar.
 */
export function OptionSelect({
  id,
  value,
  onValueChange,
  options,
  ariaLabel,
  className,
  disabled,
}: {
  id?: string;
  value: string;
  onValueChange: (value: string) => void;
  options: readonly LabelledOption[];
  ariaLabel?: string;
  className?: string;
  disabled?: boolean;
}) {
  return (
    <Select
      value={value || EMPTY}
      onValueChange={(next) => onValueChange(next === EMPTY ? "" : next)}
      disabled={disabled}
    >
      <SelectTrigger id={id} aria-label={ariaLabel} className={className}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value || EMPTY} value={option.value || EMPTY}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

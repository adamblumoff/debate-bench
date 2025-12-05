import { useEffect, useMemo } from "react";

type UpdateFn = (next: Partial<{ xField: string; yField?: string; colorField?: string }>) => void;

type Params = {
  availableFields: string[];
  xField: string;
  yField?: string;
  colorField?: string;
  setXField: (v: string) => void;
  setYField: (v: string | undefined) => void;
  setColorField: (v: string | undefined) => void;
  sendUpdate: UpdateFn;
};

export function useFieldGuards({
  availableFields,
  xField,
  yField,
  colorField,
  setXField,
  setYField,
  setColorField,
  sendUpdate,
}: Params) {
  const fieldsKey = useMemo(() => availableFields.join("|"), [availableFields]);

  useEffect(() => {
    if (!availableFields.length) return;

    let nextX = xField;
    let nextY = yField;
    let nextColor = colorField;
    let changed = false;

    if (!availableFields.includes(nextX)) {
      nextX = availableFields[0];
      setXField(nextX);
      changed = true;
    }
    if (nextY && !availableFields.includes(nextY)) {
      nextY = undefined;
      setYField(undefined);
      changed = true;
    }
    if (nextColor && !availableFields.includes(nextColor)) {
      nextColor = undefined;
      setColorField(undefined);
      changed = true;
    }

    if (changed) {
      sendUpdate({ xField: nextX, yField: nextY, colorField: nextColor });
    }
  }, [fieldsKey, availableFields, xField, yField, colorField, setXField, setYField, setColorField, sendUpdate]);
}

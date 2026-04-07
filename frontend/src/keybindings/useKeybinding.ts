/** Hook to register keyboard shortcuts in components. */

import { useEffect } from "react";
import { useKeybindingContext } from "./KeybindingContext";

export function useKeybinding(action: string, handler: () => void, deps: React.DependencyList = []) {
  const { registerAction } = useKeybindingContext();

  useEffect(() => {
    return registerAction(action, handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, registerAction, ...deps]);
}

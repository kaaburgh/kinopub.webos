import { useEffect } from 'react';

import { ButtonClickHandler, KeyboardCodesKeys, registerButtonHandler } from 'utils/keyboard';

export type { ButtonClickHandler, KeyboardCodesKeys } from 'utils/keyboard';

function useButtonEffect(key: KeyboardCodesKeys | KeyboardCodesKeys[], handler: ButtonClickHandler, priority?: number) {
  useEffect(() => {
    return registerButtonHandler(key, handler, priority);
  }, [key, handler, priority]);
}

export default useButtonEffect;

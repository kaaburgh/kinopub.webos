import { BUTTON_HANDLER_PRIORITY, registerButtonHandler, triggerButtonClick } from './keyboard';

const flushHandlers = () => new Promise<void>((resolve) => setTimeout(resolve, 0));

describe('button handler priority', () => {
  it('lets an overlay consume Back before navigation regardless of registration order', async () => {
    const calls: string[] = [];
    const unregisterOverlay = registerButtonHandler(
      'Back',
      () => {
        calls.push('overlay');
        return false;
      },
      BUTTON_HANDLER_PRIORITY.Overlay,
    );
    const unregisterNavigation = registerButtonHandler(
      'Back',
      () => {
        calls.push('navigation');
        return false;
      },
      BUTTON_HANDLER_PRIORITY.Navigation,
    );

    try {
      triggerButtonClick('Back');
      await flushHandlers();

      expect(calls).toEqual(['overlay']);
    } finally {
      unregisterOverlay();
      unregisterNavigation();
    }
  });

  it('keeps a visible overlay ahead of a later default re-registration', async () => {
    const calls: string[] = [];
    const unregisterOverlay = registerButtonHandler(
      'Back',
      () => {
        calls.push('overlay');
        return false;
      },
      BUTTON_HANDLER_PRIORITY.Overlay,
    );
    const unregisterDefault = registerButtonHandler('Back', () => {
      calls.push('default');
    });

    try {
      triggerButtonClick('Back');
      await flushHandlers();

      expect(calls).toEqual(['overlay']);
    } finally {
      unregisterOverlay();
      unregisterDefault();
    }
  });

  it('reaches navigation after a higher-priority handler declines to consume Back', async () => {
    const calls: string[] = [];
    const unregisterNavigation = registerButtonHandler(
      'Back',
      () => {
        calls.push('navigation');
        return false;
      },
      BUTTON_HANDLER_PRIORITY.Navigation,
    );
    const unregisterDefault = registerButtonHandler('Back', () => {
      calls.push('default');
    });

    try {
      triggerButtonClick('Back');
      await flushHandlers();

      expect(calls).toEqual(['default', 'navigation']);
    } finally {
      unregisterNavigation();
      unregisterDefault();
    }
  });
});

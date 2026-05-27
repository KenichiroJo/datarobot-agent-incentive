import { driver, type Driver } from 'driver.js';
import { useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

import { TOUR_LOCALSTORAGE_KEY, TOUR_STEPS, type TourStep } from '@/lib/tour-steps';

/**
 * driver.js のツアーを起動するフック。
 *
 * 戻り値の startTour() を呼ぶと:
 *   - スポットライト + バックドロップ表示
 *   - 「次へ」「戻る」「完了」「閉じる」ボタンを日本語化
 *   - ページ遷移を伴うステップは navigate() を自動実行 → DOM 待機 → 次ステップ
 *   - 完了/閉じる/スキップ で localStorage に完了フラグを保存
 */
export function useTutorialTour(): {
  startTour: () => void;
  hasCompletedTour: () => boolean;
  resetTour: () => void;
} {
  const navigate = useNavigate();
  const driverRef = useRef<Driver | null>(null);

  const startTour = useCallback(() => {
    // 既存インスタンスがあれば破棄
    if (driverRef.current) {
      driverRef.current.destroy();
    }

    const handleComplete = (): void => {
      try {
        localStorage.setItem(TOUR_LOCALSTORAGE_KEY, '1');
      } catch {
        // localStorage 利用不可な環境では無視
      }
    };

    const driverObj: Driver = driver({
      showProgress: true,
      animate: true,
      allowClose: true,
      overlayOpacity: 0.65,
      stagePadding: 6,
      stageRadius: 8,
      nextBtnText: '次へ',
      prevBtnText: '戻る',
      doneBtnText: '完了',
      progressText: '{{current}} / {{total}}',
      // ステップごとの遷移制御
      onNextClick: (_element, step, opts) => {
        const typedStep = step as TourStep;
        const targetPath = typedStep.navigateTo;
        if (targetPath) {
          navigate(targetPath);
          // ルーティング + DOM 更新を待ってから moveNext
          // (React Router v7 は同期遷移するが、Vite HMR + StrictMode で余裕を持たせる)
          setTimeout(() => {
            opts.driver.moveNext();
          }, 600);
          return;
        }
        opts.driver.moveNext();
      },
      onDestroyStarted: () => {
        handleComplete();
        driverObj.destroy();
      },
      onDestroyed: () => {
        handleComplete();
      },
      // driver.js v1.3 では steps 配列に DriveStep のみ受け取るので拡張プロパティは別管理
      steps: TOUR_STEPS.map((s) => ({
        element: s.element,
        popover: s.popover,
      })),
    });

    driverRef.current = driverObj;
    driverObj.drive();
  }, [navigate]);

  const hasCompletedTour = useCallback((): boolean => {
    try {
      return localStorage.getItem(TOUR_LOCALSTORAGE_KEY) === '1';
    } catch {
      return false;
    }
  }, []);

  const resetTour = useCallback((): void => {
    try {
      localStorage.removeItem(TOUR_LOCALSTORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  return { startTour, hasCompletedTour, resetTour };
}

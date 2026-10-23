/**
 * Mawlid an-Nabiy (Мавлид ан-Набий) - Telegram Mini App eReader Engine
 * Ultra-Fast WebP Engine with Full In-Memory Cache (0ms Instant Flipping)
 */

(() => {
  'use strict';

  // --- Telegram WebApp Bridge ---
  const tg = window.Telegram?.WebApp || null;
  if (tg) {
    tg.ready();
    tg.expand();
    if (tg.enableClosingConfirmation) {
      tg.enableClosingConfirmation();
    }
  }

  // --- Configuration & State ---
  const CONFIG = {
    totalPages: 24,
    pagePath: (num) => `/static/pages/page_${num}.webp`,
    storageKeys: {
      lastPage: 'mawlid_last_read_page',
      bookmarks: 'mawlid_bookmarks_v1',
      theme: 'mawlid_theme'
    }
  };

  const state = {
    currentPage: 1,
    totalPages: CONFIG.totalPages,
    uiVisible: true,
    theme: 'dark',
    bookmarks: [],
    touchStartX: 0,
    touchStartY: 0,
    touchStartTime: 0,
    zoomScale: 1.0,
    lastTapTime: 0
  };

  // Full in-memory image cache for instant 0ms page turns
  const pageCache = new Map();

  // --- DOM Elements ---
  const dom = {
    app: document.getElementById('app'),
    header: document.getElementById('app-header'),
    footer: document.getElementById('app-footer'),
    viewport: document.getElementById('viewport'),
    canvasWrapper: document.getElementById('canvas-wrapper'),
    pageImage: document.getElementById('page-image'),
    loadingOverlay: document.getElementById('loading-overlay'),
    loadingText: document.getElementById('loading-text'),
    pagePill: document.getElementById('page-pill'),
    
    // Controls
    btnPrev: document.getElementById('btn-prev'),
    btnNext: document.getElementById('btn-next'),
    pageSlider: document.getElementById('page-slider'),
    currentPageNum: document.getElementById('current-page-num'),
    totalPagesCount: document.getElementById('total-pages-count'),
    jumpLabel: document.getElementById('jump-label'),
    btnJumpModal: document.getElementById('btn-jump-modal'),
    btnOpenToc: document.getElementById('btn-open-toc'),
    
    // Header actions
    btnBookmark: document.getElementById('btn-bookmark'),
    btnOpenBookmarks: document.getElementById('btn-open-bookmarks'),
    btnThemeModal: document.getElementById('btn-theme-modal'),
    btnFullscreen: document.getElementById('btn-fullscreen'),
    
    // Tap zones
    tapPrev: document.getElementById('tap-prev'),
    tapToggle: document.getElementById('tap-toggle'),
    tapNext: document.getElementById('tap-next'),
    
    // Modals
    modalJump: document.getElementById('modal-jump'),
    modalBookmarks: document.getElementById('modal-bookmarks'),
    modalThemes: document.getElementById('modal-themes'),
    pageGrid: document.getElementById('page-grid'),
    bookmarksList: document.getElementById('bookmarks-list')
  };

  // --- Storage Helper ---
  const Storage = {
    async get(key, fallback = null) {
      if (tg?.CloudStorage) {
        return new Promise((resolve) => {
          tg.CloudStorage.getItem(key, (err, val) => {
            if (!err && val !== null && val !== undefined) {
              try { resolve(JSON.parse(val)); return; } catch(e) { resolve(val); return; }
            }
            try {
              const localVal = localStorage.getItem(key);
              resolve(localVal ? JSON.parse(localVal) : fallback);
            } catch (e) {
              resolve(fallback);
            }
          });
        });
      } else {
        try {
          const val = localStorage.getItem(key);
          return val ? JSON.parse(val) : fallback;
        } catch (e) {
          return fallback;
        }
      }
    },

    set(key, val) {
      const serialized = JSON.stringify(val);
      try { localStorage.setItem(key, serialized); } catch (e) {}
      if (tg?.CloudStorage) {
        try { tg.CloudStorage.setItem(key, serialized, () => {}); } catch(e) {}
      }
    }
  };

  // --- Haptics Helper ---
  function triggerHaptic(type = 'light') {
    if (tg?.HapticFeedback) {
      try {
        tg.HapticFeedback.impactOccurred(type);
      } catch (e) {}
    }
  }

  // --- Theme Management ---
  function applyTheme(newTheme) {
    state.theme = newTheme;
    document.documentElement.setAttribute('data-theme', newTheme);
    Storage.set(CONFIG.storageKeys.theme, newTheme);

    if (tg?.setHeaderColor) {
      const headerColors = { dark: '#161f2e', sepia: '#e8deca', light: '#f8fafc' };
      try { tg.setHeaderColor(headerColors[newTheme] || '#161f2e'); } catch(e) {}
    }

    document.querySelectorAll('.theme-chip').forEach(chip => {
      chip.classList.toggle('active', chip.getAttribute('data-theme-val') === newTheme);
    });
  }

  // --- Proactive Eager Preloading ---
  function preloadPage(num) {
    if (num < 1 || num > state.totalPages || pageCache.has(num)) return;
    const img = new Image();
    img.src = CONFIG.pagePath(num);
    pageCache.set(num, img);
  }

  function startBackgroundPreload(aroundPage = 1) {
    // 1. Immediately preload adjacent pages first
    for (let offset = 1; offset <= 3; offset++) {
      preloadPage(aroundPage + offset);
      preloadPage(aroundPage - offset);
    }
    // 2. Preload remaining pages progressively
    setTimeout(() => {
      for (let i = 1; i <= state.totalPages; i++) {
        preloadPage(i);
      }
    }, 600);
  }

  // --- Render Page (Instant Swap) ---
  function renderPage(pageNum) {
    if (pageNum < 1) pageNum = 1;
    if (pageNum > state.totalPages) pageNum = state.totalPages;

    state.currentPage = pageNum;
    state.zoomScale = 1.0;
    resetZoom();

    // Immediately update UI indicators so user sees their click registered!
    updateUIElements();

    const targetSrc = CONFIG.pagePath(pageNum);
    const cachedImg = pageCache.get(pageNum);

    if (cachedImg && cachedImg.complete && cachedImg.naturalWidth > 0) {
      // In-memory instant swap (0 milliseconds)
      dom.pageImage.src = targetSrc;
      dom.loadingOverlay.classList.add('hidden');
    } else {
      // Show fast visual feedback while downloading
      dom.loadingText.textContent = `Саҳифа ${pageNum} юкланмоқда...`;
      dom.loadingOverlay.classList.remove('hidden');

      const loader = new Image();
      loader.onload = () => {
        if (state.currentPage === pageNum) {
          dom.pageImage.src = targetSrc;
          dom.loadingOverlay.classList.add('hidden');
        }
      };
      loader.onerror = () => {
        dom.loadingOverlay.classList.add('hidden');
      };
      loader.src = targetSrc;
      pageCache.set(pageNum, loader);
    }

    // Trigger page flip animation
    dom.canvasWrapper.classList.remove('page-flip-anim');
    void dom.canvasWrapper.offsetWidth;
    dom.canvasWrapper.classList.add('page-flip-anim');

    // Preload surrounding pages
    startBackgroundPreload(pageNum);

    // Persist position
    Storage.set(CONFIG.storageKeys.lastPage, state.currentPage);
  }

  // --- UI Updates ---
  function updateUIElements() {
    const cur = state.currentPage;
    const total = state.totalPages;

    dom.currentPageNum.textContent = cur;
    dom.totalPagesCount.textContent = total;
    dom.pageSlider.value = cur;
    dom.pageSlider.max = total;
    dom.jumpLabel.textContent = `Саҳифа ${cur} / ${total}`;
    dom.pagePill.textContent = `${cur} / ${total}`;

    dom.btnPrev.disabled = cur <= 1;
    dom.btnNext.disabled = cur >= total;

    const isBookmarked = state.bookmarks.includes(cur);
    dom.btnBookmark.classList.toggle('active', isBookmarked);
    const bookmarkSvg = dom.btnBookmark.querySelector('svg');
    if (bookmarkSvg) {
      bookmarkSvg.setAttribute('fill', isBookmarked ? 'currentColor' : 'none');
    }

    document.querySelectorAll('.page-grid-item').forEach(item => {
      const p = parseInt(item.getAttribute('data-page'), 10);
      item.classList.toggle('active', p === cur);
    });
  }

  // --- Zoom Handling ---
  function resetZoom() {
    dom.pageImage.style.transform = `scale(${state.zoomScale})`;
  }

  function toggleZoom() {
    state.zoomScale = state.zoomScale > 1.2 ? 1.0 : 1.75;
    resetZoom();
    triggerHaptic('medium');
  }

  // --- Navigation Actions ---
  function nextPage() {
    if (state.currentPage < state.totalPages) {
      triggerHaptic('light');
      renderPage(state.currentPage + 1);
    }
  }

  function prevPage() {
    if (state.currentPage > 1) {
      triggerHaptic('light');
      renderPage(state.currentPage - 1);
    }
  }

  function goToPage(p) {
    const target = Math.max(1, Math.min(state.totalPages, parseInt(p, 10) || 1));
    triggerHaptic('medium');
    renderPage(target);
  }

  function toggleControls() {
    state.uiVisible = !state.uiVisible;
    dom.header.classList.toggle('hidden', !state.uiVisible);
    dom.footer.classList.toggle('hidden', !state.uiVisible);
    dom.pagePill.classList.toggle('hidden', state.uiVisible);
  }

  // --- Bookmarks Logic ---
  function toggleCurrentBookmark() {
    const page = state.currentPage;
    const idx = state.bookmarks.indexOf(page);
    if (idx >= 0) {
      state.bookmarks.splice(idx, 1);
      triggerHaptic('warning');
    } else {
      state.bookmarks.push(page);
      state.bookmarks.sort((a, b) => a - b);
      triggerHaptic('success');
    }
    Storage.set(CONFIG.storageKeys.bookmarks, state.bookmarks);
    updateUIElements();
    renderBookmarksList();
  }

  function renderBookmarksList() {
    dom.bookmarksList.innerHTML = '';
    if (state.bookmarks.length === 0) {
      dom.bookmarksList.innerHTML = `
        <div class="empty-state">
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
          </svg>
          <div style="font-size: 15px; font-weight: 600;">Ҳозирча хатчўплар йўқ</div>
          <div style="font-size: 13px;">Саҳифани сақлаш учун юқоридаги 🔖 тугмасини босинг.</div>
        </div>
      `;
      return;
    }

    state.bookmarks.forEach(page => {
      const item = document.createElement('div');
      item.className = 'bookmark-item';
      item.innerHTML = `
        <div class="bookmark-info">
          <span class="bookmark-page-badge">Саҳифа ${page}</span>
          <span style="font-weight: 600; font-size: 14px;">Мавлид ан-Набий</span>
        </div>
        <button class="bookmark-delete-btn" title="Ўчириш" data-delete-page="${page}">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"></polyline>
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
          </svg>
        </button>
      `;

      item.addEventListener('click', (e) => {
        if (e.target.closest('.bookmark-delete-btn')) {
          e.stopPropagation();
          state.bookmarks = state.bookmarks.filter(p => p !== page);
          Storage.set(CONFIG.storageKeys.bookmarks, state.bookmarks);
          updateUIElements();
          renderBookmarksList();
          triggerHaptic('warning');
          return;
        }
        closeModal(dom.modalBookmarks);
        goToPage(page);
      });

      dom.bookmarksList.appendChild(item);
    });
  }

  // --- Modal Helpers ---
  function openModal(modalEl) {
    modalEl.classList.add('open');
    if (tg?.BackButton) {
      tg.BackButton.show();
      tg.BackButton.onClick(() => closeModal(modalEl));
    }
  }

  function closeModal(modalEl) {
    modalEl.classList.remove('open');
    if (tg?.BackButton) {
      tg.BackButton.hide();
    }
  }

  function setupModals() {
    dom.pageGrid.innerHTML = '';
    for (let i = 1; i <= state.totalPages; i++) {
      const tile = document.createElement('div');
      tile.className = 'page-grid-item';
      tile.setAttribute('data-page', i);
      tile.innerHTML = `
        <span>${i}</span>
        <span class="label">бет</span>
      `;
      tile.addEventListener('click', () => {
        closeModal(dom.modalJump);
        goToPage(i);
      });
      dom.pageGrid.appendChild(tile);
    }

    document.querySelectorAll('[data-close]').forEach(btn => {
      btn.addEventListener('click', () => {
        const modalId = btn.getAttribute('data-close');
        const modal = document.getElementById(modalId);
        if (modal) closeModal(modal);
      });
    });

    [dom.modalJump, dom.modalBookmarks, dom.modalThemes].forEach(modal => {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal(modal);
      });
    });

    document.querySelectorAll('.theme-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const val = chip.getAttribute('data-theme-val');
        applyTheme(val);
        triggerHaptic('light');
      });
    });
  }

  // --- Gestures Setup ---
  function setupGestures() {
    dom.tapPrev.addEventListener('click', () => prevPage());
    dom.tapNext.addEventListener('click', () => nextPage());
    
    dom.tapToggle.addEventListener('click', (e) => {
      const now = Date.now();
      if (now - state.lastTapTime < 300) {
        toggleZoom();
      } else {
        toggleControls();
      }
      state.lastTapTime = now;
    });

    // Touch swipe
    dom.viewport.addEventListener('touchstart', (e) => {
      if (e.touches.length === 1) {
        state.touchStartX = e.touches[0].clientX;
        state.touchStartY = e.touches[0].clientY;
        state.touchStartTime = Date.now();
      }
    }, { passive: true });

    dom.viewport.addEventListener('touchend', (e) => {
      if (e.changedTouches.length === 1) {
        const deltaX = e.changedTouches[0].clientX - state.touchStartX;
        const deltaY = e.changedTouches[0].clientY - state.touchStartY;
        const elapsed = Date.now() - state.touchStartTime;

        if (Math.abs(deltaX) > 40 && Math.abs(deltaX) > Math.abs(deltaY) * 1.5 && elapsed < 500) {
          if (deltaX < 0) {
            nextPage();
          } else {
            prevPage();
          }
        }
      }
    }, { passive: true });

    // Keyboard navigation
    window.addEventListener('keydown', (e) => {
      switch (e.key) {
        case 'ArrowRight':
        case 'PageDown':
        case ' ':
          e.preventDefault();
          nextPage();
          break;
        case 'ArrowLeft':
        case 'PageUp':
        case 'Backspace':
          e.preventDefault();
          prevPage();
          break;
        case 'Home':
          e.preventDefault();
          goToPage(1);
          break;
        case 'End':
          e.preventDefault();
          goToPage(state.totalPages);
          break;
        case 'Escape':
          [dom.modalJump, dom.modalBookmarks, dom.modalThemes].forEach(m => closeModal(m));
          break;
      }
    });
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    dom.btnPrev.addEventListener('click', () => prevPage());
    dom.btnNext.addEventListener('click', () => nextPage());

    dom.pageSlider.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      dom.currentPageNum.textContent = val;
      dom.jumpLabel.textContent = `Саҳифа ${val} / ${state.totalPages}`;
    });

    dom.pageSlider.addEventListener('change', (e) => {
      const val = parseInt(e.target.value, 10);
      goToPage(val);
    });

    dom.btnBookmark.addEventListener('click', () => toggleCurrentBookmark());
    dom.btnOpenBookmarks.addEventListener('click', () => {
      renderBookmarksList();
      openModal(dom.modalBookmarks);
    });

    dom.btnJumpModal.addEventListener('click', () => openModal(dom.modalJump));
    dom.btnOpenToc.addEventListener('click', () => openModal(dom.modalJump));
    dom.btnThemeModal.addEventListener('click', () => openModal(dom.modalThemes));

    dom.btnFullscreen.addEventListener('click', () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    });

    dom.pageImage.addEventListener('load', () => {
      dom.loadingOverlay.classList.add('hidden');
    });
  }

  // --- App Initialization ---
  async function init() {
    setupEventListeners();
    setupGestures();
    setupModals();

    const [savedTheme, savedBookmarks, savedLastPage] = await Promise.all([
      Storage.get(CONFIG.storageKeys.theme, 'dark'),
      Storage.get(CONFIG.storageKeys.bookmarks, []),
      Storage.get(CONFIG.storageKeys.lastPage, 1)
    ]);

    applyTheme(savedTheme);
    state.bookmarks = Array.isArray(savedBookmarks) ? savedBookmarks : [];

    const initialPage = Math.min(Math.max(1, parseInt(savedLastPage, 10) || 1), state.totalPages);
    
    // Start proactive in-memory background download for all 24 pages
    startBackgroundPreload(initialPage);

    renderPage(initialPage);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();

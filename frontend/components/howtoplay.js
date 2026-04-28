// components/howtoplay.js — How to Play modal

const HowToPlay = (() => {
  let currentSlide = 0;
  const totalSlides = 6;

  function init() {
    document.getElementById('btnHowToPlay').addEventListener('click', open);
    document.getElementById('btnHowToPlaySetup').addEventListener('click', open);
    document.getElementById('htpModalClose').addEventListener('click', close);
    document.getElementById('htpModal').addEventListener('click', (e) => {
      if (e.target === document.getElementById('htpModal')) close();
    });

    document.getElementById('htpNext').addEventListener('click', () => goTo(currentSlide + 1));
    document.getElementById('htpPrev').addEventListener('click', () => goTo(currentSlide - 1));

    buildDots();
    goTo(0);

    // Keyboard
    document.addEventListener('keydown', (e) => {
      const modal = document.getElementById('htpModal');
      if (!modal.classList.contains('visible')) return;
      if (e.key === 'ArrowRight') goTo(currentSlide + 1);
      if (e.key === 'ArrowLeft')  goTo(currentSlide - 1);
      if (e.key === 'Escape')     close();
    });
  }

  function open() {
    document.getElementById('htpModal').classList.add('visible');
    goTo(0);
  }

  function close() {
    document.getElementById('htpModal').classList.remove('visible');
  }

  function buildDots() {
    const container = document.getElementById('htpDots');
    container.innerHTML = '';
    for (let i = 0; i < totalSlides; i++) {
      const dot = document.createElement('div');
      dot.className = 'htp-dot';
      dot.addEventListener('click', () => goTo(i));
      container.appendChild(dot);
    }
  }

  function goTo(index) {
    currentSlide = Math.max(0, Math.min(totalSlides - 1, index));

    document.querySelectorAll('.htp-slide').forEach((s, i) => {
      s.classList.toggle('active', i === currentSlide);
    });

    document.querySelectorAll('.htp-dot').forEach((d, i) => {
      d.classList.toggle('active', i === currentSlide);
    });

    document.getElementById('htpPrev').disabled = currentSlide === 0;
    document.getElementById('htpNext').textContent =
      currentSlide === totalSlides - 1 ? 'Got it! →' : 'Next →';

    if (currentSlide === totalSlides - 1) {
      document.getElementById('htpNext').addEventListener('click', close, { once: true });
    }
  }

  return { init, open, close };
})();
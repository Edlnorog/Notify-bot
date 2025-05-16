document.addEventListener('DOMContentLoaded', function() {
    const rows = document.querySelectorAll('.resources-row');
    
    rows.forEach((row, index) => {
        // Задержка для эффекта "лесенки" - каждый следующий ряд с задержкой 200ms
        setTimeout(() => {
            const cards = row.querySelectorAll('.resources-card');
            cards.forEach(card => {
                card.classList.add('resources-show');
            });
        }, index * 200);
    });
});
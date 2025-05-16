function toggleCard(card) {
    const container = card.parentElement;
    const allCards = container.querySelectorAll('.participants-card');
    
    if (card.classList.contains('active')) {
        // Если карточка уже активна, возвращаем все карточки в исходное состояние
        allCards.forEach(c => {
            c.classList.remove('active');
            c.classList.remove('hidden');
        });
    } else {
        // Иначе скрываем все карточки, кроме выбранной
        allCards.forEach(c => {
            if (c === card) {
                c.classList.add('active');
            } else {
                c.classList.add('hidden');
            }
        });
    }
}
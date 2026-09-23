document.addEventListener('DOMContentLoaded', () => {
    
    // Sidebar active configuration toggle handling
    const navItems = document.querySelectorAll('.sidebar-nav ul li');
    
    navItems.forEach(item => {
        item.addEventListener('click', function(e) {
            // Check to ensure we are clicking on actual links
            if(this.closest('ul').classList.contains('sidebar-footer') && this.textContent.includes('Log out')) {
                return; // Let logout skip styling changes
            }
            
            navItems.forEach(i => i.classList.remove('active'));
            this.classList.add('active');
        });
    });

    // Back click helper interaction 
    const backButton = document.querySelector('.back-btn');
    if(backButton) {
        backButton.addEventListener('click', () => {
            alert('Navigating back to main menu window...');
        });
    }

    // Dynamic Class Card Click Interactions
    const cards = document.querySelectorAll('.class-card');
    cards.forEach(card => {
        card.addEventListener('click', function() {
            const className = this.querySelector('h3').textContent;
            console.log(`Loading metrics overview for Standard ${className}...`);
        });
    });
});
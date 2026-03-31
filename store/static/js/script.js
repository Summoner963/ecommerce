'use strict';

// Helper function for debouncing
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Keep track of scroll state
let isScrollLocked = false;

// Helper function to manage scroll locking
function toggleScroll(lock) {
    if (lock === isScrollLocked) return;
    
    isScrollLocked = lock;
    document.body.style.overflow = lock ? 'hidden' : '';
    document.body.style.position = lock ? 'fixed' : '';
    document.body.style.width = lock ? '100%' : '';
    
    // Preserve scroll position when unlocking
    if (!lock) {
        const scrollY = document.body.style.top;
        document.body.style.position = '';
        document.body.style.top = '';
        window.scrollTo(0, parseInt(scrollY || '0') * -1);
    }
}

// Initialize all interactive elements
function initializeElements() {
    // Modal handling
    const modal = document.querySelector('[data-modal]');
    const modalCloseBtn = document.querySelector('[data-modal-close]');
    const modalOverlay = document.querySelector('[data-modal-overlay]');

    if (modal && modalCloseBtn && modalOverlay) {
        const closeModal = () => {
            modal.classList.add('closed');
            toggleScroll(false);
        };
        const openModal = () => {
            modal.classList.remove('closed');
            toggleScroll(true);
        };
        
        modalCloseBtn.addEventListener('click', closeModal);
        modalOverlay.addEventListener('click', closeModal);
        modal.addEventListener('show', openModal);
    }

    // Toast notifications
    const notificationToast = document.querySelector('[data-toast]');
    const toastCloseBtn = document.querySelector('[data-toast-close]');

    if (notificationToast && toastCloseBtn) {
        toastCloseBtn.addEventListener('click', () => {
            notificationToast.classList.add('closed');
        });
    }

    // Mobile menu handling
    const mobileMenu = document.querySelector('[data-mobile-menu]');
    const openMenuBtns = document.querySelectorAll('[data-mobile-menu-open-btn]');
    const closeMenuBtn = document.querySelector('[data-mobile-menu-close-btn]');
    const overlay = document.querySelector('[data-overlay]');

    if (mobileMenu) {
        const openMenu = () => {
            mobileMenu.classList.add('active');
            overlay?.classList.add('active');
            toggleScroll(true);
        };

        const closeMenu = () => {
            mobileMenu.classList.remove('active');
            overlay?.classList.remove('active');
            toggleScroll(false);
        };

        openMenuBtns.forEach(btn => {
            btn.addEventListener('click', openMenu);
        });

        closeMenuBtn?.addEventListener('click', closeMenu);
        overlay?.addEventListener('click', closeMenu);
    }

    // Accordion handling
    const handleAccordionClick = (e) => {
        const accordionBtn = e.target.closest('[data-accordion-btn]');
        if (!accordionBtn) return;

        const accordion = accordionBtn.nextElementSibling;
        const allAccordions = document.querySelectorAll('[data-accordion]');
        const allAccordionBtns = document.querySelectorAll('[data-accordion-btn]');

        // Close all other accordions
        allAccordions.forEach((acc, index) => {
            if (acc !== accordion && acc.classList.contains('active')) {
                acc.classList.remove('active');
                allAccordionBtns[index].classList.remove('active');
            }
        });

        // Toggle clicked accordion
        accordion?.classList.toggle('active');
        accordionBtn.classList.toggle('active');
    };

    document.addEventListener('click', handleAccordionClick);
}

// Update live counts for cart and wishlist
function updateCounts() {
    const updateCount = (endpoint, elementIds) => {
        fetch(endpoint)
            .then(response => response.json())
            .then(data => {
                elementIds.forEach(id => {
                    const element = document.getElementById(id);
                    if (element) element.textContent = data.count;
                });
            })
            .catch(error => console.error('Error fetching counts:', error));
    };

    updateCount('/cart/count/', ['cart-count', 'cart-count-mobile']);
    updateCount('/wishlist/count/', ['wishlist-count', 'wishlist-count-mobile']);
}

// Handle adding to cart functionality
function handleCartActions() {
    document.querySelectorAll('.add-to-cart-btn, .home-add-to-cart-btn').forEach(button => {
        button.addEventListener('click', event => {
            event.preventDefault();
            const form = button.closest('form');
            
            if (!form) return;

            const productId = form.getAttribute('action').split('/').pop();
            const csrfToken = form.querySelector('[name=csrfmiddlewaretoken]')?.value;

            const formData = new FormData();
            formData.append('quantity', 1);

            // Try to get default color if exists
            const defaultColorInput = document.querySelector(`input[name="default_color_${productId}"]`);
            if (defaultColorInput) {
                formData.append('color', defaultColorInput.value);
            }

            fetch(form.getAttribute('action'), {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    alert(data.message || 'Product added to cart!');
                    updateCounts();
                } else {
                    alert(data.error || 'Failed to add product to cart');
                }
            })
            .catch(error => {
                console.error('Error adding to cart:', error);
                alert('There was a problem adding the product to cart');
            });
        });
    });
}

// Handle color selection and image updates
function initializeColorSelection() {
    const colorButtons = document.querySelectorAll('.color-btn');
    const carouselTrack = document.querySelector('.carousel__track');
    const indicators = document.querySelectorAll('.carousel__indicator');

    if (!carouselTrack || !colorButtons.length) return;

    colorButtons.forEach(button => {
        button.addEventListener('click', () => {
            const selectedColor = button.dataset.color;
            if (!selectedColor) return;

            const productSlug = document.querySelector('[data-product-slug]')?.dataset.productSlug;
            if (!productSlug) return;

            fetch(`/product/${productSlug}/images/${selectedColor}/`)
                .then(response => response.json())
                .then(data => {
                    if (!data.images?.length) return;

                    // Update carousel images
                    carouselTrack.innerHTML = data.images
                        .map((img, index) => `
                            <li class="carousel__slide ${index === 0 ? 'current-slide' : ''}">
                                <img src="${img.url}" alt="${img.alt}" class="carousel__image">
                            </li>
                        `).join('');

                    // Update indicators
                    indicators.forEach((indicator, idx) => {
                        const img = indicator.querySelector('img');
                        if (img && data.images[idx]) {
                            img.src = data.images[idx].url;
                        }
                        indicator.classList.toggle('current-slide', idx === 0);
                    });
                })
                .catch(error => console.error('Error updating images:', error));
        });
    });

    // Default to the first color
    colorButtons[0]?.click();
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded',() => {
    initializeElements();
    updateCounts();
    handleCartActions();
  });
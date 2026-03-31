// Burger Menu
const burger = document.querySelector('.burger');
const navLinks = document.querySelector('.nav-links');
const pageMask = document.querySelector('.page-mask');

burger.addEventListener('click', () => {
    navLinks.classList.toggle('showMenu');
    burger.classList.toggle('showMenu');
    pageMask.classList.toggle('showMenu');
    // Fix: Toggle body scroll when menu is open
    document.body.style.overflow = document.body.style.overflow === 'hidden' ? '' : 'hidden';
});

// Carousel
const track = document.querySelector('.carousel__track');
const slides = Array.from(track?.children || []);
const nextButton = document.querySelector('.carousel__button-container--next');
const prevButton = document.querySelector('.carousel__button-container--prev');
const indicatorsNav = document.querySelector('.carousel__indicator-container');
const indicators = Array.from(indicatorsNav?.children || []);

// Only initialize carousel if elements exist
if (track && slides.length > 0) {
    // find the width to move
    const slideWidth = slides[0].getBoundingClientRect().width;

    // Setting the slides in position
    const setSlidePosition = (slide, index) => {
        slide.style.left = slideWidth * index + 'px';
    }

    slides.forEach(setSlidePosition);

    // moveToSlide function
    const moveToSlide = (track, currentSlide, targetSlide) => {
        if (!track || !currentSlide || !targetSlide) return;
        track.style.transform = 'translateX(-' + targetSlide.style.left + ')';
        currentSlide.classList.remove('current-slide');
        targetSlide.classList.add('current-slide');
    }

    const updateIndicators = (currentIndi, targetIndi) => {
        if (!currentIndi || !targetIndi) return;
        currentIndi.classList.remove('current-slide');
        targetIndi.classList.add('current-slide');
    };

    // Show/Hide arrows function
    const showHideArrows = (targetIndex, prevButton, nextButton, slides) => {
        if (!prevButton || !nextButton) return;
        if (targetIndex === 0) {
            prevButton.classList.add('is-hidden');
            nextButton.classList.remove('is-hidden');
        } else if (targetIndex === slides.length - 1) {
            prevButton.classList.remove('is-hidden');
            nextButton.classList.add('is-hidden');
        } else {
            prevButton.classList.remove('is-hidden');
            nextButton.classList.remove('is-hidden');
        }
    }

    // Event Listeners
    if (prevButton) {
        prevButton.addEventListener('click', e => {
            const currentSlide = track.querySelector('.current-slide');
            const prevSlide = currentSlide?.previousElementSibling;
            if (!prevSlide) return;
            
            const currentIndi = indicatorsNav?.querySelector('.current-slide');
            const prevIndi = currentIndi?.previousElementSibling;
            const prevIndex = slides.findIndex(slide => slide === prevSlide);
            
            moveToSlide(track, currentSlide, prevSlide);
            updateIndicators(currentIndi, prevIndi);
            showHideArrows(prevIndex, prevButton, nextButton, slides);
        });
    }

    if (nextButton) {
        nextButton.addEventListener('click', e => {
            const currentSlide = track.querySelector('.current-slide');
            const nextSlide = currentSlide?.nextElementSibling;
            if (!nextSlide) return;
            
            const currentIndi = indicatorsNav?.querySelector('.current-slide');
            const nextIndi = currentIndi?.nextElementSibling;
            const nextIndex = slides.findIndex(slide => slide === nextSlide);

            moveToSlide(track, currentSlide, nextSlide);
            updateIndicators(currentIndi, nextIndi);
            showHideArrows(nextIndex, prevButton, nextButton, slides);
        });
    }

    if (indicatorsNav) {
        indicatorsNav.addEventListener('click', e => {
            const targetIndi = e.target.closest('div');
            if (!targetIndi) return;

            const currentSlide = track.querySelector('.current-slide');
            const currentIndi = indicatorsNav.querySelector('.current-slide');
            const targetIndex = indicators.findIndex(dot => dot === targetIndi);
            const targetSlide = slides[targetIndex];

            moveToSlide(track, currentSlide, targetSlide);
            updateIndicators(currentIndi, targetIndi);
            showHideArrows(targetIndex, prevButton, nextButton, slides);
        });
    }
}

// Cart functionality
const showHideCart = document.querySelector('.my-cart');
const myCart = document.querySelector('.cart-container');

if (myCart) {
    myCart.addEventListener('click', e => {
        e.preventDefault(); // Fix: Added parentheses
        showHideCart?.classList.toggle('showMyCart');
        // Fix: Toggle body scroll when cart is open
        document.body.style.overflow = 
            showHideCart?.classList.contains('showMyCart') ? 'hidden' : '';
    });
}

// Quantity Controls
const plus = document.querySelector('.plus-container');
const minus = document.querySelector('.minus-container');
const quantity = document.querySelector('.quantity__num');
const cartContainer = document.querySelector('.my-cart__items-container');
const emptyCart = document.querySelector('.my-cart__items');
const cart = document.querySelector('.my-cart-not-empty');
const addToCartBtn = document.querySelector('.to-cart');
const checkoutBtn = document.querySelector('.checkout-button');
const deleteBtn = document.querySelector('.delete-img');
const cartPrice = document.querySelector('.cart-price');
const cartNum = document.querySelector('.cart__num');

let currentQuantity = 0;
if (quantity) quantity.innerText = currentQuantity;

// Functions
const minusQuantity = () => {
    if (currentQuantity > 0) {
        currentQuantity -= 1;
        if (quantity) quantity.innerText = currentQuantity;
    }
};

const plusQuantity = () => {
    if (currentQuantity < 10) {
        currentQuantity += 1;
        if (quantity) quantity.innerText = currentQuantity;
    }
};

const addToCart = () => {
    if (!cart || !checkoutBtn || !cartPrice || !emptyCart || !cartNum) return;
    
    if (currentQuantity > 0) {
        cart.style.display = 'flex';
        checkoutBtn.style.display = 'block';
        cartPrice.innerHTML = 
            `$125.00 x ${currentQuantity} <span>$${currentQuantity * 125}.00</span>`;
        emptyCart.style.display = 'none';
        cartNum.style.display = 'flex';
        cartNum.innerHTML = String(currentQuantity);
    } else {
        cart.style.display = 'none';
        emptyCart.style.display = 'flex';
        checkoutBtn.style.display = 'none';
        cartNum.style.display = 'none';
    }
};

const deleteCartItem = () => {
    if (!cart || !emptyCart || !checkoutBtn || !cartNum) return;
    
    cart.style.display = 'none';
    emptyCart.style.display = 'flex';
    checkoutBtn.style.display = 'none';
    cartNum.style.display = 'none';
    currentQuantity = 0; // Fix: Changed === to =
    if (quantity) quantity.innerText = currentQuantity;
};

// Event listeners
minus?.addEventListener('click', minusQuantity);
plus?.addEventListener('click', plusQuantity);
addToCartBtn?.addEventListener('click', addToCart);
deleteBtn?.addEventListener('click', deleteCartItem);

// Remove debug interval
// setInterval(() => {
//     console.log('Body overflow:', document.body.style.overflow);
//     console.log('HTML overflow:', document.documentElement.style.overflow);
// }, 1000);
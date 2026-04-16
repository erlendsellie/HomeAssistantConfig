// ==UserScript==
// @name         Inatur UI Helper
// @namespace    http://tampermonkey.net/
// @version      1.9
// @description  Automatisert søknadshjelp for Inatur. Fjernet innloggingssjekk og optimalisert for fart.
// @author       User
// @match        https://www.inatur.no/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const wait = (ms) => new Promise(r => setTimeout(r, ms));
    const Q_DATA = 'in_session_data';

    async function setupSequence(list) {
        if (!Array.isArray(list) || list.length === 0) return;
        localStorage.setItem(Q_DATA, JSON.stringify(list));
        nextInSequence();
    }

    function nextInSequence() {
        const d = localStorage.getItem(Q_DATA);
        if (!d) return;

        let q = JSON.parse(d);
        if (q.length === 0) {
            localStorage.removeItem(Q_DATA);
            alert("✅ Alle søknader ferdigstilt!");
            return;
        }

        const next = q.shift();
        localStorage.setItem(Q_DATA, JSON.stringify(q));

        const url = new URL(next, window.location.origin);
        url.searchParams.set('v', '2'); 
        url.searchParams.set('seq', '1');
        window.location.href = url.toString();
    }

    async function processPage() {
        // Vent kort på React
        await wait(1500);

        let items = [];
        const cards = document.querySelectorAll('.kortliste .kort, #kortliste .kort, article.kort');
        
        for (let c of cards) {
            const ps = Array.from(c.querySelectorAll('p'));
            const isMatch = ps.find(p => p.textContent.trim().toLowerCase() === 'søknad');
            if (isMatch || c.innerText.includes("Søknad")) items.push(c);
        }

        if (items.length > 0) {
            for (let item of items) {
                // Scroll og klikk
                item.scrollIntoView({ behavior: 'auto', block: 'center' });
                await wait(400);

                if (!item.classList.contains('valgt')) {
                    item.click();
                    await wait(800);
                }

                const uBtn = document.querySelector('label[for^="prioritet-UTENBYGDS"], #prioritet-UTENBYGDS, input[value="UTENBYGDS"]');
                if (uBtn) {
                    uBtn.click();
                    await wait(300);
                }

                const sBtn = document.querySelector('button#sokPaKort, button.kjop, .sokPaKort button');
                if (sBtn && !sBtn.disabled && sBtn.offsetParent !== null) {
                    sBtn.click();
                    await wait(800);
                }
            }
        }

        const params = new URLSearchParams(window.location.search);
        if (params.get('seq') === '1' || params.has('v2')) {
            await wait(1000);
            nextInSequence();
        } else if (params.get('close') === '1') {
            window.close();
        }
    }

    window.StartSequence = setupSequence;

    function init() {
        const params = new URLSearchParams(window.location.search);
        if (params.has('v2')) {
            try {
                const list = JSON.parse(atob(params.get('v2')));
                setupSequence(list);
            } catch (e) {
                processPage();
            }
            return;
        }
        if (params.get('v') === '2' || params.get('seq') === '1') {
            processPage();
        }
    }

    init();
})();

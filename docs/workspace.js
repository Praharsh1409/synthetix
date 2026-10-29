'use strict';
const frame = document.querySelector('iframe');
const note = document.getElementById('connection-note');
frame.addEventListener('load', () => {
  // A frame load cannot prove that a remote application started successfully.
  note.textContent = 'If the workspace is blank or your browser blocks embedded apps, open Synthetix in a new tab above.';
});

// jsdom has no native dialog implementation; browser tests exercise real focus behavior.
HTMLDialogElement.prototype.showModal = function () { this.setAttribute('open', '') }
HTMLDialogElement.prototype.close = function () { this.removeAttribute('open') }

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('#changelist-filter input[type="text"]').forEach(function (input) {
        var name = input.name || '';
        if (name.endsWith('__gte') || name.endsWith('__lte') || input.placeholder === 'From' || input.placeholder === 'To') {
            input.type = 'date';
        }
    });
});

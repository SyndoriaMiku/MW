(function($) {
    $(document).ready(function() {
        $(document).on('formset:added', function(event, $row, formsetName) {
            // Check if this row belongs to our Lumen Ascend Rules by looking for lumen_level input
            var $currentLevelInput = $row.find('input[name$="-lumen_level"]');
            
            if ($currentLevelInput.length > 0) {
                var $prevRow = $row.prevAll('.dynamic-form:first'); // In tabular inline, dynamic-form class is used or form-row
                if ($prevRow.length === 0) {
                    $prevRow = $row.prev('.form-row');
                }
                
                if ($prevRow.length > 0) {
                    var $prevCheckboxes = $prevRow.find('input[type="checkbox"]:checked');
                    $prevCheckboxes.each(function() {
                        var value = $(this).val();
                        $row.find('input[type="checkbox"][value="' + value + '"]').prop('checked', true);
                    });
                    
                    // Auto-increment level
                    var $prevLevelInput = $prevRow.find('input[name$="-lumen_level"]');
                    if ($prevLevelInput.length > 0) {
                        var prevVal = parseInt($prevLevelInput.val(), 10);
                        if (!isNaN(prevVal)) {
                            $currentLevelInput.val(prevVal + 1);
                        }
                    }
                }
            }
        });
    });
})(django.jQuery);

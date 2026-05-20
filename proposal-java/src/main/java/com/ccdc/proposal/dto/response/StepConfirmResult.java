package com.ccdc.proposal.dto.response;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class StepConfirmResult {
    private boolean success;
    private String message;
    private int currentStep;
    private boolean hasNext;
}

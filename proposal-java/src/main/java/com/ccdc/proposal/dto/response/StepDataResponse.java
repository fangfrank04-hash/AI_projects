package com.ccdc.proposal.dto.response;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class StepDataResponse {
    private int stepId;
    private Object content;
    private String sessionId;
}

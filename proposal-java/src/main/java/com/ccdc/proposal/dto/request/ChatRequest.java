package com.ccdc.proposal.dto.request;

import lombok.Data;

@Data
public class ChatRequest {
    private String message;
    private String sessionId;
    private Integer currentStep;
    private Object draftData;
}

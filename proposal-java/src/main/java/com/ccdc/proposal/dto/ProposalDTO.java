package com.ccdc.proposal.dto;

import lombok.Data;

@Data
public class ProposalDTO {
    private Long id;
    private String projectId;
    private Integer currentStep;
    private String completedSteps;
    private String status;
    private String confirmedBy;
    private Object steps;
}

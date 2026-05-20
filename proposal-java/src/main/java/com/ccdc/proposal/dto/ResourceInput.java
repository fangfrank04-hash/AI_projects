package com.ccdc.proposal.dto;

import lombok.Data;

@Data
public class ResourceInput {
    private String totalWorkload;
    private String totalDuration;
    private String internalWorkload;
    private String personnelOutsourcing;
    private String projectOutsourcing;
}

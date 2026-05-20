package com.ccdc.proposal.dto.request;

import lombok.Data;
import java.util.Map;

@Data
public class CheckRequest {
    private Map<String, Object> proposalData;
}

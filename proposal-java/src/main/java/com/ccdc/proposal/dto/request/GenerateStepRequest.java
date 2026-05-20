package com.ccdc.proposal.dto.request;

import lombok.Data;
import java.util.Map;

@Data
public class GenerateStepRequest {
    private Map<String, Object> params;
}

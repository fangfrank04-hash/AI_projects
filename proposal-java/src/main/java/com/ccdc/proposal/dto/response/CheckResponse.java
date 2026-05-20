package com.ccdc.proposal.dto.response;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class CheckResponse {
    private boolean passed;
    private List<CheckItem> items;

    @Data
    @NoArgsConstructor
    @AllArgsConstructor
    public static class CheckItem {
        private String name;
        private String status; // pass / warn / fail
        private String message;
    }
}

package com.ccdc.proposal.dto;

import com.ccdc.proposal.entity.ResponsibilityItem;
import lombok.Data;
import java.util.List;

@Data
public class TeamMemberData {
    private String role;
    private String name;
    private List<ResponsibilityItem> responsibilities;
}

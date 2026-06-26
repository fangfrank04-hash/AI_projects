package com.ccdc.proposal.config;

import com.ccdc.proposal.entity.*;
import com.ccdc.proposal.repository.*;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

import java.util.List;

@Component
public class DataInitializer implements ApplicationRunner {

    private final ProjectRepository projectRepository;
    private final TeamMemberRepository teamMemberRepository;
    private final KnowledgeRepository knowledgeRepository;

    public DataInitializer(ProjectRepository projectRepository,
                           TeamMemberRepository teamMemberRepository,
                           KnowledgeRepository knowledgeRepository) {
        this.projectRepository = projectRepository;
        this.teamMemberRepository = teamMemberRepository;
        this.knowledgeRepository = knowledgeRepository;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (projectRepository.count() > 0) return;

        Project p = new Project();
        p.setId("P001");
        p.setName("测试项目");
        p.setDept("技术部");
        p.setLevel("A级");
        p.setPmName("张三");
        p.setProductName("测试产品");
        p.setReqDept("业务部");
        p.setStatus("待确认");
        p = projectRepository.save(p);

        TeamMember tm1 = new TeamMember();
        tm1.setProject(p);
        tm1.setRole("产品经理");
        tm1.setName("李四");
        tm1.setResponsibilities(List.of(
                new ResponsibilityItem("需求分析", true),
                new ResponsibilityItem("产品设计", true)));

        TeamMember tm2 = new TeamMember();
        tm2.setProject(p);
        tm2.setRole("开发工程师");
        tm2.setName("王五");
        tm2.setResponsibilities(List.of(
                new ResponsibilityItem("编码实现", true),
                new ResponsibilityItem("单元测试", true)));

        TeamMember tm3 = new TeamMember();
        tm3.setProject(p);
        tm3.setRole("测试工程师");
        tm3.setName("赵六");
        tm3.setResponsibilities(List.of(
                new ResponsibilityItem("功能测试", true),
                new ResponsibilityItem("回归测试", true)));

        teamMemberRepository.saveAll(List.of(tm1, tm2, tm3));

        KnowledgeRule kr1 = new KnowledgeRule();
        kr1.setProjectLevel("A级");
        kr1.setRuleType("team");
        kr1.setRuleContent("{\"min_roles\":3,\"standard_roles\":[\"产品经理\",\"开发工程师\",\"测试工程师\"]}");
        kr1.setVersion("1.0");
        kr1.setIsActive(true);

        KnowledgeRule kr2 = new KnowledgeRule();
        kr2.setProjectLevel("A级");
        kr2.setRuleType("control");
        kr2.setRuleContent("{\"required_phases\":[\"开发\",\"测试\",\"结项\"],\"optional_phases\":[\"需求分析\",\"项目评审\"]}");
        kr2.setVersion("1.0");
        kr2.setIsActive(true);

        knowledgeRepository.saveAll(List.of(kr1, kr2));

        System.out.println("Seed data initialized: " + teamMemberRepository.count() + " team members");
    }
}
